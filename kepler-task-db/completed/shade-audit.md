# shade-audit (Software/Systems, $300) — BUILT + local-green 2026-09-14, HELD

## task.toml
```toml
artifacts = ["/app/findings.json"]

[task]
name = "afterquery/shade-audit"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "This is the third party clearance a release engineer or product security reviewer runs before a proprietary java product ships, when the deliverable is a single shaded uber jar built by the maven shade plugin and the question is which of the known advisories against the bundled libraries actually apply to what leaves the building. It is hard because shading breaks every shortcut a normal software composition audit relies on. The plugin relocates some packages, so a library is present in the artifact under a renamed package and a search for the advisory's own class path finds nothing. It minimizes the jar, so a library that is listed in every record, and still carries its own pom.properties inside the jar, has had its classes stripped out and is not shipped at all, while another library keeps some classes and loses exactly the one an advisory names. Two libraries can define the same class and only one survives the merge, so the class that ships may be the safe one that never had the vulnerable method. The hand kept sbom disagrees with the artifact in both directions at once, naming a safe version where the build actually resolved an affected one and an affected version where it resolved a safe one, and omitting a library that got pulled in transitively. None of this is visible from the records. The reviewer has to open the jar, read the versions the build really resolved from the retained maven metadata, decide presence one class at a time against the actual class entries, and read the shipped bytecode to see whether the member an advisory turns on is even there. Every naive reading, trusting the sbom, grepping for the original package, treating a listed component as shipped, or a present class as vulnerable, lands wrong on a different set of advisories, and there is no build to re run and no tool that takes the policy and the jar and returns the set, so no candidate answer can be checked against anything. For a person it is a couple of hours of careful bytecode archaeology across a dozen advisories where one misread class throws the whole set. The shipped jar and records are synthetic but the jar is a genuine maven shade plugin build with real relocation, real minimize pruning and a real class collision, so the artifact behaves exactly as a production shaded jar does."
solution_explanation = "The verdict for each advisory is derived from the delivered product.jar alone, never from the sbom. List the actual class entries in the jar. For each advisory, decide whether the affected class is really present, accounting for relocation by matching on the trailing package and class name rather than the original path, and per class so a minimized-away class counts as absent even though its component's pom.properties is still in the jar. If the advisory names a required symbol, read the shipped class with javap and confirm the member is actually declared, which rules out an overwritten class from a collision merge and a version that patched the method out. Take the shipped version from the jar's own META-INF/maven pom.properties, not the sbom, and test it against the advisory's affected range. An advisory applies only when the class is present, the symbol is present, and the resolved version is affected. The sbom is a deliberate distractor: it names a safe version for a library the build resolved to an affected one, an affected version for one it resolved to a safe one, and leaves out a transitively bundled library entirely. Six of the twelve advisories apply."
verification_explanation = "The deliverable is data, so the verifier runs nothing the agent produced and needs no jvm. It loads /app/findings.json, requires an object with the single key applicable mapping to a list of advisory id strings with no duplicates and no id outside the twelve in the register, then compares that set to a sealed answer.json baked into the verifier image and never present in the agent container. Grading is one exact set over all twelve advisories, all or nothing, so an advisory that should be flagged and is left off and one flagged that is fine as shipped fail identically and there is no partial credit. The sealed answer was produced by the reference reconciliation over the shipped jar and cross checked so that every naive baseline misses it in both directions. The verifier runs in its own separate container after the agent container is torn down, the answer file is unreadable from the agent image, and reward.txt is written on every code path including a crash."
category = "Software"
subcategory = "Systems"
tags = ["java", "supply-chain", "bytecode", "forensics", "compliance"]
expert_time_estimate_hours = 6
relevant_experience = "I have run release engineering and third party clearance for shipped java products, including software composition and license review on fat and shaded jars built with the maven shade plugin. That work is exactly this: shading relocates and minimizes and merges classes, so the build metadata and the shipped bytecode drift apart from any sbom, and clearing an advisory means opening the artifact with jar and javap, reading the resolved versions from the retained maven descriptors, and deciding presence and reachability one class at a time rather than trusting the inventory."

[verifier]
timeout_sec = 120.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
```

## instruction.md
```
we ship product.jar to customers and i cannot let this release out the door until the third party code in it is cleared. it is a shaded uber jar. everything bundled into the one file. our security team keeps a register of known issues in the libraries we pull in, and i need to know which of those issues actually bite the thing we ship, not the thing our paperwork thinks we ship.

it all sits under /app. `/app/product.jar` is the release jar. `/app/advisories.tsv` is the register, one row per advisory, giving the component, the rule for which versions are affected, the affected class, and the member that has to be present for the issue to matter. `/app/sbom.tsv` is our hand kept dependency inventory. read `/app/POLICY.md` first. that is DSR-6, it says what counts as applying to what we actually ship, and it does not settle any single advisory for you.

here is the part that makes this real work and not a lookup. the jar and the records do not agree. shade relocates packages and strips out classes nothing calls and the inventory was typed up by hand months ago, so a row in a record proves nothing on its own. i learned this the hard way on the last release when a clean looking sbom sent me chasing a library that was not even in the artifact. so work each advisory against the jar itself.

write `/app/findings.json`. one object, one key `applicable`, the advisory ids that apply, as strings:

    {"applicable": ["ADV-201", "ADV-207"]}

it is graded as a set against the list i cut by hand, all or nothing. one you leave off that should be on it, and one you put on it that ships fine, are the same mistake to me. order and whitespace do not matter. no duplicates. do not pad it for safety and do not trim it to look tidy.

nothing else you write is kept. only `/app/findings.json` comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
