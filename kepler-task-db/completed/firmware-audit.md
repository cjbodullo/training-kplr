# firmware-audit

## task.toml
```toml
artifacts = ["/app/findings.json"]

[task]
name = "afterquery/firmware-audit"

[metadata]
author_name = "Shaswat Panda"
author_email = "pandashaswat712@gmail.com"
difficulty_explanation = "Clearing a field firmware update before it ships is the work a product security or firmware supply-chain analyst does when a vendor hands over an update package and asks whether the rootfs inside it is only the approved production build. The delivered artifact is a real U-Boot FIT image (.itb) built with the ordinary embedded toolchain: a kernel, a devicetree, and two squashfs root filesystems wired through a multi-configuration FIT, plus the vendor's release build-record (component id, expected sha256, version) and a production allowlist (approved component ids, per-component minimum version) carried as a detached RSA-signed file with its public key. What makes each verdict real work rather than a lookup is that the rootfs files carry no component identity at all: a file is just a path and its bytes, and the only way to learn what component and version a file is comes from hashing its content and finding that hash in the build-record, which is a separate document that never names a path. So authorization for one file crosses three sources that do not reference each other, the extracted rootfs, the build-record, and the signed allowlist, and none of the three settles it alone. The FIT ships two rootfs images and the older decoy is listed first, so reading the default configuration to pick the production image is load-bearing before a single file is judged. Inside the production rootfs the evidence does not line up: a file sits at an ordinary system path but its bytes hash to nothing in the record, an approved component is present but at a version below the allowlist minimum, an approved component's bytes appear at an unexpected path, two files share identical bytes, a component absent from the signed allowlist is present, and a second unsigned allowlist planted in the rootfs would flip several verdicts if it were trusted instead of the signed one. None of that can be read off a path or a filename. Grading is an exact set of rootfs paths and one reading in either direction, a file wrongly cleared or a clean file wrongly flagged, is the whole task. The package, its records and the answer are built for this review, so none of it is online. For an expert it is a careful pass with the FIT, the record and the signed policy all open at once, and the difficulty is the job's own: the mechanisms are in front of you and the verdict for each file is not."
solution_explanation = "Verify the detached signature over /app/allowlist.json with /app/signing_pub.pem; the signed allowlist is authoritative and the unsigned /etc/approved.conf later found in the rootfs is a decoy. Read /configurations/default in /app/firmware.itb, follow it to that configuration's ramdisk image name, and extract THAT image (not the first image, which is an older decoy rootfs) with the FIT tooling, then unsquashfs it in a scratch dir. Load /app/build-record.csv as a map from sha256 to (component id, version). For every regular file in the extracted rootfs, hash its bytes: a hash absent from the record is a tampered or unknown file and is unauthorized; otherwise take the file's component id and version from the record and clear it only when that component is on the signed allowlist and its version is at least the component's minimum. Path is never the key, so an approved component's bytes at an odd path and a duplicated approved file both clear, while an approved component rolled back below its minimum and a component missing from the allowlist do not. The unauthorized set is seven paths: /usr/sbin/sshd and /usr/sbin/dropbear and /usr/lib/libpng-min.so (bytes hash to nothing in the record, tampered), /usr/lib/libssl-lite.so (present but at a version below the allowlist minimum), /usr/bin/telnetd and /usr/bin/debugd (present, hash-known, but not approved by the signed allowlist), and /etc/approved.conf (the planted rogue allowlist, itself not a known build artifact). The authorized files that stay off the list include the relocated-but-legitimate /opt/vendor/acme/libparse.so, the duplicate /usr/share/recovery/logtool.bak, and /usr/lib/libz-emb.so, which the signed allowlist approves and the decoy omits. Write the sorted paths as {\"unauthorized\": [...]} to /app/findings.json."
verification_explanation = "The deliverable is data, so the verifier executes nothing the agent wrote, extracted or built. It json.loads /app/findings.json, checks it is an object carrying an \"unauthorized\" list of rootfs-absolute paths as strings with no duplicates and every path one of the known rootfs files, and compares that list as a set against a sealed answer baked into the verifier image and never present in the agent container. A missing path and an extra path fail identically, so over-reporting and under-reporting both score zero and grading is all or nothing over the rootfs files. The sealed set was produced by the generator that built the FIT image, the two squashfs root filesystems and the records, and is independently reproduced by the reference, which reads only the material shipped to the agent, resolves the default FIT configuration, extracts and unsquashes the production rootfs with the real toolchain and joins hashes to the build-record, so the answer is derivable from the evidence alone rather than planted. The verifier runs in its own separate container, the answer file is unreadable from the agent image, the reward directory is root owned and reward.txt carries exactly 0 or 1 on every path including a crash."
category = "Security"
subcategory = "Forensics"
tags = ["firmware", "supply-chain", "forensics", "squashfs", "reverse-engineering"]
expert_time_estimate_hours = 6
relevant_experience = "I have reviewed vendor firmware updates for a hardware product and sat in the release gate that decides whether an update image can go to the field. The part that is never a checklist is establishing what a file actually is when the filesystem tells you nothing but a path and some bytes: you unpack the image the bootloader would actually pick, hash what is really on it, and reconcile that against the build ledger and the signed component policy, and those three disagree more often than anyone likes. I have caught a rolled-back library that was present and looked fine, a binary swapped under an approved path, and a second allowlist planted in a rootfs that would have cleared exactly the thing it was meant to hide."

[verifier]
timeout_sec = 300.0
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
we got a field firmware update from the odm and i need it cleared before it goes out. the package is `/app/firmware.itb`. it is a fit image, the kernel and the devicetree and the root filesystem are all packed inside it, and the rootfs is a squashfs. pull the rootfs the package is actually configured to boot and work off that one.

what i want back is the set of files in that rootfs we cannot account for as approved, current, untampered production code. our production component allowlist is `/app/allowlist.json`. it is signed, the detached signature is `/app/allowlist.json.sig` and the key is `/app/signing_pub.pem`, so you can confirm it is ours before you trust it. the release build ledger is `/app/build-record.csv`. that is how a file maps to a component and a version. the filesystem does not carry component identity, a file is a path and its bytes and nothing else.

write `/app/findings.json`. one object, one key `unauthorized`, the rootfs paths that are not approved production files, absolute inside the rootfs like `/usr/bin/foo` or `/lib/libbar.so`:

    {"unauthorized": ["/usr/sbin/something", "/usr/lib/other.so"]}

i grade it as a set against the list i worked out by hand. all or nothing. a file that belongs on the list and is left off, and a clean file you put on it, are the same mistake. order and whitespace do not matter, no duplicates. do not pad it and do not trim it.

the image, the ledger and the signed allowlist will not always agree. reconciling them is the job. nothing else you leave behind is kept, only `/app/findings.json` comes back.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
