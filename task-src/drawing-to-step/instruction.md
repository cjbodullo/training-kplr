we took over spares for six parts whose vendors are gone and all we have are their old prints. they were hand drawn on paper. somebody vectorized the scans, so what sits in `/app/drawings` is dxf where every dimension is just lines and arrowheads and all the lettering came out as outlines, not text. the parts we need are BRK-2210, FLG-0417, HSG-3305, SHF-1150, CVR-5120 and BKT-3302. our cnc programmer only works from 3d, so i need a STEP model of each of those, true size, in mm.

careful. nothing on these prints is to scale, the dimensions govern and you can't measure off the geometry. read the title block and notes of every sheet.

put each model at `/app/models/<part no>.step`, so `/app/models/BRK-2210.step`, `/app/models/FLG-0417.step`, `/app/models/HSG-3305.step`, `/app/models/SHF-1150.step`, `/app/models/CVR-5120.step` and `/app/models/BKT-3302.step`. one solid per file. how you place it in the file is up to you, just keep the main faces square to the model axes.

shop conventions for the model. nominal size everywhere, ignore fit classes like H7 or k6 and the general tolerances. drilled and tapped holes get the drill diameter at the drill depth the callout gives, flat bottom, no thread and no drill point. edge break and deburr notes are not modelled. everything else on the print is.

each model gets checked against the vendor's original solid and every surface has to be within 0.02 mm of it. one feature off on one part fails the lot.

You have 18000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
