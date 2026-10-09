# phi-residue — completed bundle manifest (v2)

## task.toml
```toml
artifacts = ["/app/findings.json"]

[task]
name = "afterquery/phi-residue"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the release-clearance review a hospital imaging core or a research data steward runs before a batch of studies leaves for an outside collaborator, and it is judged on both sides: name a file that is fine and the release slips while someone re-checks it by hand, miss one and the group ships a patient's name, a real record number, a reversible date or a re-linkable source reference to an outside party. The material is 62 synthetic dicom files built for this review across 16 patients, valid instances the standard dicom toolchain parses, with generated ct rasters (a smooth phantom plus acquisition noise, and on a few files a bright caption band painted into the pixels), overlay planes, private data blocks, a structured report, nested reference sequences and per patient shifted dates. What makes it work and not a lookup is that the decision runs on the group's own rule, RDX-4, which is deliberately not the standard de-identification profile and states the principles but not the disposition of any file, and on what is actually inside each file rather than on the record that describes it. The vendor scrub log states a disposition per file and is wrong in both directions, so it cannot be read off. Identifying material does not sit only in the obvious top level elements: it is pushed into a private data element under a scanner vendor's creator, into an overlay plane, into the pixel raster as a burned-in band that no text dump reveals while the annotation flag says there is none, into the content tree of a structured report, into a nested referenced-study item, or into a source instance reference that only resolves to a real study once it is joined against the crosswalk. The date reasoning is a reconciliation, not a scan: across a patient's several studies the shift must be one offset, so a study on a different offset or never shifted breaks the timeline, and within a single study the date elements must agree, so one element left at its true value is a partial shift that no single tag reveals. Several things that look identifying are cleared, a retained calibration block that reads like leaked private data, a genuine pseudonym in the identity slot, a private creator declared with no values, a reference that resolves to nothing in the crosswalk, a date that is present but shifted correctly, so a strategy that flags every anomaly over-reports. Nothing in the container decides it: no tool takes a policy and a pile of files and returns the set. Grading is an exact set over the 62 files and one reading in either direction is the whole task. The files, the crosswalk, the log and the answer are built for this review, so none of it is online. The skill that carries it is knowing where identity actually survives a scrub and which of the survivals the group's own rule still forbids, held over 62 files at once."
solution_explanation = "Read POLICY.md for the frame and settle each of the 62 files from the file itself, never from scrub_log.tsv, which is unreliable. Walk every file completely: the top level elements, every element nested inside a sequence item, the private blocks, the overlay groups, the report content tree and the pixel data. A file is withheld when it carries identifying material RDX-4 does not clear, and 15 of the 62 do. The mechanisms, each producing findings and each with a matching trap that must stay off: (1) person names, any element whose value representation is PN must be empty except the patient identity and patient name slots, which may hold only the RDX-#### pseudonym, so a real name under a private creator, in a referring-physician element or in a nested study item is withheld while a genuine pseudonym is fine. (2) the patient id slot, a real record number there rather than the pseudonym is withheld. (3) private data, a value under any private creator other than RDXCAL is withheld, while the RDXCAL calibration block and a private creator declared with no values are fine. (4) overlay planes in group 60xx are withheld. (5) burned-in annotation, found by reading the raster and detecting a bright block far above the phantom and noise rather than by trusting the annotation flag, is withheld, while a file the log calls burned-in whose raster is clean is fine. (6) a structured report content tree is withheld. (7) a source reference is withheld when its instance uid appears as an original in uid_registry.csv and fine when it does not. (8) dates, joining each study to its original date in the crosswalk gives a per-study offset; grouping by patient, a study whose offset does not match its patient's shared offset or is zero is withheld, and within a study the date elements must all carry the same shifted date, so one left at the true value is a partial shift and is withheld. The withheld set is the union of these across the corpus, fifteen files; the reference reproduces it from /app alone."
verification_explanation = "The deliverable is data, so the verifier executes nothing the agent wrote or built and needs no dicom toolchain. It json.loads /app/findings.json, checks it is an object carrying a single withheld list of file ids that are strings, with no duplicates and every id one of the 62 known files, and compares that list as a set against a sealed answer baked into the verifier image and never present in the agent container. A missing file and an extra file fail identically, so over-reporting and under-reporting both score zero and grading is all or nothing over the 62 files. The sealed set was produced by the generator that built the corpus and is independently reproduced by the reference, which reads only the material shipped to the agent and inspects the same files, so the answer is derivable from the evidence alone rather than planted. The verifier runs in its own separate container, the answer file is unreadable from the agent image, the reward directory is root owned and reward.txt is written on every path including a crash."
category = "Security"
subcategory = "Forensics"
tags = ["dicom", "de-identification", "phi", "medical-imaging", "data-privacy"]
expert_time_estimate_hours = 8
relevant_experience = "I have run de-identification pipelines for a clinical imaging archive and sat on the release side of a data use agreement, where the job is not to run the standard profile but to prove a specific batch is clean under our own rule. The part that is never a checklist is knowing where identity actually survives a scrub: a name a technologist typed into a private element, an accession left in a referenced-study item, a report whose narrative was never touched, an overlay that a viewer burns over the image, pixels with the patient's name rendered into them, and dates that were shifted per study instead of per patient so the intervals give the calendar back. I have argued both directions in a release review, that a file full of scary looking private tags is fine because they are our calibration block, and that a file the tool called clean is not, because the name is one sequence level down."

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1200.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md
```
we are releasing a batch of imaging studies to an outside collaborator and it cannot go out until the identifying material is gone. a vendor scrub tool already ran over it. i do not trust the result. i need the list of files that still carry something we are not allowed to release.

the exported studies are the dicom files under `/app/export`, one `.dcm` per file. the file id is the name without the extension. our own crosswalk is `/app/uid_registry.csv`, which maps each released instance back to its original instance uid and original study date. `/app/RELEASE.txt` has the cut date and which tool ran. `/app/scrub_log.tsv` is that tool's per file disposition. it is a record of what it thought it did and it is wrong both ways, so treat it as noise, not truth.

read `/app/POLICY.md` first. that is RDX-4, our clearance rule, and it is not the standard de-identification profile. it says what counts as the released material, the three narrow allowances (the assigned pseudonym, the retained calibration block, the per patient date shift), and what is forbidden outright. it sets the frame. it does not tell you the disposition of any single file. you work each file out yourself against what is actually in it.

the thing that matters here is that identifying material does not sit only in the obvious top level tags. it hides. a blanked patient name does not mean the name is gone from the file. so a value can sit in a nested sequence item, in a private data element, in an overlay plane, in the pixels, in a report body, or in a source reference that resolves back to a real study. the released material is all of it.

write `/app/findings.json`. one object, one key `withheld`, whose value is the list of file ids (exactly as they appear under `/app/export`, no `.dcm`) that are not clear for release:

    {"withheld": ["some_id", "another_id"]}

it is graded as a set against the list i cut by hand, all or nothing. a file that should be held and is left off, and a file on the list that is fine to ship, are the same mistake. order and whitespace do not matter, no duplicates, do not pad it and do not trim it.

nothing else you write is kept. only `/app/findings.json` comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
