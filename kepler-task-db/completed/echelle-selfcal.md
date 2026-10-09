# echelle-selfcal (submitted dcqLz9A7EbP83jCbwVlQ, 2026-07-28)

## task.toml
```toml
artifacts = ["/app/reduce.py"]

[task]
name = "afterquery/echelle-selfcal"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
The standard chain is necessary and nowhere near sufficient. Bias, a linearity \
ladder, a master flat, traces, slit tilt, a wavelength solution from the arc, \
optimal extraction with the sky fitted along the slit, per exposure dispersion \
drift from the sky lines: an agent that does all of that correctly still lands \
around 5 percent on the graded metric, against a bar of 2.5 percent. The reason \
is that this detector fringes, and the fringe pattern a point source lays down \
is not the pattern the flat field lamp lays down, because the lamp and the sky \
fill the pupil and a star does not. No flat, taken at any temperature or any \
time, removes a star's fringes. Measured: 0.049 to 0.072 uncorrected, which is \
two to three times the bar on its own. \
Getting past it needs three things that do not appear in any reduction \
cookbook. The star is the same in every exposure while the fringes move between \
them, so dividing one exposure by another cancels the star exactly and leaves \
pure fringe, which is what pins the point source amplitudes. The two flat sets \
sit at different recorded detector temperatures, which gives the thermal \
coefficient of the etalon phase outright instead of having to infer it. And the \
fringes are fixed to the detector, not to the sky, so when the dispersion \
drifts the pattern slides underneath the spectrum: the correction has to be \
evaluated at the wavelength of the column the light landed on, not at the \
wavelength of the spectrum. Missing that last point alone leaves most of the \
fringe in place. \
There is no feedback of any kind. The container holds no truth, no reference \
spectrum and no scorer, so an agent cannot tell a good pipeline from a plausible \
wrong one by running anything. Grading is on a night the pipeline has never \
seen, so nothing can be tuned to the shipped frames. Every order of every \
exposure has to clear the bar, so one systematic left in one order scores zero.
"""
solution_explanation = """
Read the manual, then build the chain in the order the physics runs backwards \
in. Master bias from the bias frames. The nonlinearity comes out of the flat \
ladder, because true signal is proportional to exposure time and any curvature \
against time is the detector; fit measured = s - B s^2 on a fixed pixel set and \
invert in closed form. Master flat from the bright flats after that inversion. \
Traces from the collapsed flat, slit tilt by maximising the sharpness of the \
collapsed arc lines, wavelength solution per order by matching centroided arc \
peaks to the shipped line list and fitting a quadratic. \
Per exposure: subtract the scattered light fitted through the inter order gaps, \
measure the dispersion drift by centroiding sky lines in the outer slit rows and \
taking the median displacement against the sky line list, then resample every \
row onto a common wavelength grid in flux density units, fit the sky along the \
slit and extract optimally. \
Then the fringes. Take the extended pattern off the master flat at fixed \
detector column, fit its OPD, harmonic weight and per order amplitude. The \
second flat set gives the thermal coefficient. For each science exposure the \
phase then follows from its recorded temperature. What is left is the point \
source amplitude and harmonic weight, which come from ratios between exposures, \
where the star cancels. Apply the correction at the detector column wavelength. \
The reference reaches 0.011 against a 0.025 bar.
"""
verification_explanation = """
The verifier builds three fresh nights at verify time from seeds that appear \
nowhere in the environment or the bundle, each of a different target, so there \
is nothing to fit to and nothing to fabricate. Each graded night carries a \
single science exposure. That is deliberate: with several exposures of the same \
star an agent can average them and wash the fringes out without ever modelling \
them, which measured 0.021 against a 0.025 bar and would have made the central \
difficulty optional. With one exposure there is nothing to average, and the \
same uncorrected pipeline sits at 0.066. It also matches how the task is posed: \
the instrument is characterised once on the shipped night and those constants \
are carried in the pipeline. Truth is computed inside the grading process from the \
sealed instrument model and is never written to disk. \
The agent's pipeline is imported and run by a separate unprivileged process \
(uid 65534) in a scratch directory with a neutral working directory; it \
receives only a path to the night and communicates only by printing JSON on \
stdout. The sealed generator, the truth and the tolerance live under /tests at \
mode 0700 owned by root, so the agent's process cannot read them, and the \
pass/fail decision is taken in the trusted parent from numbers it recomputes \
itself. reward.txt is written from pytest's exit code on every path, including \
a crash before pytest starts, so a forged result from the child is ignored. \
Grading: for each science exposure and each order, both the returned spectrum \
and the truth are divided by their own running median continuum, the first and \
last 40 bins are dropped, and the relative rms of the difference must be at or \
under 0.025. Overall scale cancels in the continuum division, so flux \
calibration is deliberately not graded. Every order of every exposure must \
pass. Measured over six independent nights the reference lands at 0.0110 to 0.0141 \
worst order, and 0.0110 on a single exposure night, while skipping any one \
correction fails: fringes 0.066, slit tilt 0.107, flat field 0.047, dispersion \
drift 0.042 to 0.051.
"""
category = "Software"
subcategory = "Data engineering"
tags = ["data-reduction", "spectroscopy", "instrument-calibration", "signal-processing", "python", "numpy"]
expert_time_estimate_hours = 10
relevant_experience = """
I have written and maintained reduction pipelines for cross dispersed echelle \
spectrographs, which is where this task comes from. The systematics in it are \
the ones that actually cost you nights: a detector whose response bends before \
you reach full well, a slit whose image is not parallel to the columns, a \
dispersion solution that walks with temperature between the arc and the science \
frames, and fringing in the red orders. \
The specific thing this task is built on is real and is the sort of thing that \
is learned rather than read: fringe amplitude depends on how the pupil is \
filled, so a point source and a flat field lamp do not fringe alike and \
defringing a stellar spectrum with a lamp flat leaves a residual you cannot \
flat away. The way out is to use the fact that the object is constant across a \
night while the instrument state is not. I have built the cross exposure \
machinery that exploits exactly that, and the replay harnesses used to prove a \
pipeline against synthetic data before it is trusted on real frames, which is \
what the verifier here is.
"""

[verifier]
timeout_sec = 7200.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1200.0
cpus = 2
memory_mb = 6144
storage_mb = 10240
gpus = 0
```

## instruction.md
```markdown
i need a working reduction for harpe 5. one night of it is sitting in `/app/night`. start with `/app/night/MANUAL.md`, that is the instrument doc, it says what every frame in `frames.npz` is and what the headers carry.

the deliverable is `/app/reduce.py`. one func in it:

```
reduce(run_dir) -> dict
```

`run_dir` is a directory laid out exactly like `/app/night`. give me back a dict keyed by science exposure name (`sci_01` and so on), and under each one a dict keyed by order index as an int, 0 through 3, holding the extracted object spectrum as a plain list of floats. one value per bin. the bin grid per order is in `bins.json` as `lam_start`, `lam_step`, `n_bins`, so the list you hand back for an order has to be exactly `n_bins` long. object only. the sky has to come off.

here is the part people get wrong so i am saying it early. i am not grading you on this night. i point your `reduce` at a different night from the same instrument, exposures you have never seen, same layout, different target. so a script that reads these six frames and prints numbers i can already compute is worth nothing to me. it has to be a pipeline.

and the night i point it at is short. usually a single science exposure, sometimes two. this night has six because it is the one i characterised the instrument on. so anything you can only work out by comparing exposures against each other, work out here and carry it in your code. on the graded night you will not have the company.

on scoring. per exposure per order i divide your spectrum by its own running median continuum, do the same to the truth, and take rms of the difference. every order of every exposure has to land at or under `0.025`. i drop the first and last 40 bins of each order before i take that rms, the continuum estimate is no good at the ends. one order over and the whole thing is a fail, there is no partial credit. overall scale per order does not matter at all, the continuum divide eats it, so do not waste time on absolute flux.

and there is no truth in this container. nothing here will score you. no answer key, no reference spectrum, nothing that tells you whether the thing you just wrote is any good. you have the frames and the manual and that is the whole of it. i know that is uncomfortable. it is also the actual job, this is what it is like the first time an instrument comes back with data on it.

within a night it is one star all the way through, every exposure the same target. across nights it is not, we point at whatever is on the programme. so nothing about the object itself carries over.

python3 is there with numpy and scipy. nothing else needed. `/app/reduce.py` is what i collect, nothing else you leave behind is looked at.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
```
