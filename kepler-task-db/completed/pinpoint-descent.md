artifacts = ["/app/controller.py"]

[task]
name = "afterquery/pinpoint-descent"

[metadata]
author_name = "Sayan Banerjee"
author_email = "sayanbanerjee.writodesk@gmail.com"
difficulty_explanation = """
Nothing here can be transcribed. The plant is fully disclosed, so the work is \
not understanding the rules, it is hitting a performance bar under them, and \
the bar sits where a textbook controller does not reach. Measured on this \
build: a constant acceleration suicide burn with PD loops on attitude and \
lateral position, which is the first thing a competent engineer writes, lands \
60 percent. The bar is 95 percent. Closing that gap took me four structural \
changes, none of which show up until you look at the touchdown states of the \
failures. First, ignition timing has to come from forward simulation that \
carries the mass loss, because the vehicle sheds a fifth of its mass during \
the burn and the constant acceleration estimate lights early and pays for it. \
Second, minimum throttle out-accelerates gravity, so a burn that arrives at \
zero sink rate above the pad cannot idle or relight in time and instead flies \
the vehicle back up until the tank is dry. The terminal profile has to be one \
that never stops the vehicle in mid air. Third, lateral authority is thrust \
times sine of tilt, so it halves when the throttle drops for terminal descent. \
An approach planned on the acceleration available at the top of the burn \
cannot stop itself and arrives ten metres downrange. Fourth, the airframe \
takes most of a second to swing, so the lateral loop has to lead the attitude \
loop or it switches too late and overshoots the pad at fifteen metres a \
second. Each of those is worth ten to twenty points of landing rate and each \
one is invisible in the mean. Wind is unobserved and has to be estimated from \
the vehicle's own response, against velocity noise that makes a single step \
difference forty times larger than the signal. The internet does not help: \
lossless convexification and the published powered descent literature assume \
a continuously throttleable engine with no relight limit, which is exactly \
what this vehicle does not have.
"""
solution_explanation = """
Four pieces. Ignition is decided by integrating the vertical channel forward \
at the plant's own step size, with mass depletion, the throttle ramp and the \
ignition fuel cost included, and lighting when that integration says a full \
throttle burn would arrive at the terminal gate with the wanted sink rate. \
Above the gate the throttle is re-solved every step by bisecting on the lowest \
setting that still makes the gate, which self corrects against wind, tilt \
losses and noise. Below 60 m the controller stops chasing a target point and \
tracks a sink rate profile v(y) = -sqrt(v_td^2 + 2 a y), which by construction \
never reaches zero above the ground, so the vehicle cannot get trapped in the \
no hover region. Lateral is two problems, not one: above the gate a minimum \
effort intercept nulls offset and velocity by the time the gate arrives, below \
it a PD holds station against the wind while the vehicle stands up, and both \
run on a state extrapolated forward by 0.6 s to cover the attitude swing. Wind \
is recovered by a two state filter over horizontal velocity and disturbance \
acceleration, driven by the thrust component the controller knows it \
commanded. Reference performance is 599 landings in 600 episodes, and 40 of \
40 on the sealed set.
"""
verification_explanation = """
The verifier never runs the agent's file in its own interpreter. Each of the \
40 sealed episodes is integrated in the trusted grader process, while the \
controller is loaded by a separate child interpreter started as the \
unprivileged runner account, in a scratch directory that contains only a copy \
of the controller and the protocol child, with an environment whose PYTHONPATH \
does not reach /tests. The two exchange one json line per 0.05 s step: an \
observation down, three numbers back. So the simulator, the episode \
parameters, the wind profile and the landing decision are all on a side the \
controller cannot touch, and monkeypatching the plant in the child changes \
nothing. /tests is root owned mode 0700 and a test asserts the runner account \
cannot read it. Episodes come from a seed base that exists only in the \
verifier image. Grading requires at least 38 of 40 touchdowns inside all five \
tolerances at once, each from a trajectory that actually ran, and reward.txt \
is written by test.sh from pytest's exit code in the root process, so a \
forged reward file is overwritten. Confirmed locally: the reference scores 40 \
of 40, the shipped stub 0, a controller that hunts the filesystem for the \
episode parameters 0, one that monkeypatches the simulator 0, and one that \
writes its own reward file 0.
"""
category = "Science"
subcategory = "Robotics"
tags = ["control", "guidance", "simulation", "robotics", "optimization"]
expert_time_estimate_hours = 7
relevant_experience = """
I work on guidance and control for autonomous vehicles, which is where this \
task comes from. Most of my time goes on the part this task is built around: \
a control law that looks correct on a nominal trajectory and then loses the \
tail of the distribution to actuator limits nobody modelled, in this case a \
throttle that cannot idle below a floor, an engine that cannot be relit on \
demand, and an airframe whose attitude bandwidth sets how fast the outer loop \
is allowed to be. I have built simulation harnesses like this one for \
regression testing controllers over seeded disturbance draws, and the failure \
I have seen most often in that work is exactly the one this task grades \
against: a controller tuned until the mean looks good, shipped, and then \
losing five percent of runs to a coupling between axes that the mean never \
showed.
"""

[verifier]
timeout_sec = 3600.0
environment_mode = "separate"

[agent]
timeout_sec = 14400.0

[environment]
build_timeout_sec = 1200.0
cpus = 4
memory_mb = 4096
storage_mb = 10240
gpus = 0

--- instruction.md ---

the vehicle in `/app/lander/sim.py` cannot land itself. that is your job. write the guidance into `/app/controller.py`, which is sitting there stubbed with the two names i call, `reset(config)` and `act(obs)`.

read sim.py first. all of it. it is the actual plant i grade against and not a simplified copy of one, so the constants in `VEHICLE` at the top are the real numbers and the docstring tells you the frame and which way `theta` tips the thrust. i have watched people lose an afternoon to that sign.

`act` gets one observation per step and gives back three numbers, `(throttle, gimbal, rcs)`. step is 0.05 s. throttle is the engine command, gimbal is the engine deflection in radians, rcs is a body torque in newton metres from the attitude thrusters. obs is a dict, keys are `t`, `step`, `x`, `y`, `vx`, `vy`, `theta`, `omega`, `fuel`, `engine_on`, `throttle`, `gimbal`, `ignitions_used`, `lockout_remaining`. position and velocity and attitude come to you noisy. fuel and the engine bookkeeping do not. `reset` runs once before every episode with the dict `sim.config()` returns, which is vehicle constants and limits and where the pad is, and nothing about the episode itself. i start a fresh process for each episode so nothing you stash in a global survives to the next one.

what counts as a landing is narrow and it is all or nothing per episode. at the moment the vehicle touch the ground its horizontal offset, both velocities, tilt and rotation rate have to be inside `touch_x`, `touch_vx`, `touch_vy`, `touch_theta` and `touch_omega`, every one of them at once. miss any single one and it is a crash. you can also lose an episode before then by tipping past `tilt_limit`, by straying out of the approach corridor once you are under `glide_below`, or by burning through the step limit.

the engine is where this gets awkward and i am not going to pretend otherwise. anything you command under `u_min` is a shutdown, not a low idle. you get `max_ignitions` lights, each one costs fuel and each restart is locked out for `lockout_steps` after the previous shutdown. minimum throttle still pushes harder than the vehicle weighs, which is the part that catches people out, so there is no hovering and no hanging around at low power to think about it. the throttle also cannot jump, `u_rate` is the most it moves per step, and the gimbal has both a range and a rate. wind is not in the observation and i am not going to hand it to you.

grading is forty episodes drawn with `make_episode` exactly the way you can draw them, on seeds that do not appear anywhere in this image. thirty eight of the forty have to land. that is the whole score, one or zero, and thirty seven is a failure with no credit for how close the other three were.

`/app/evaluate.py` flies your controller over a seed range and prints the landing rate plus the touchdown state of everything that failed. `python3 /app/evaluate.py 1 200` for instance. pick whatever seeds you want, they come from the same draw as mine. a rate measured over twenty episodes tells you almost nothing here, and the failures are not one failure repeated, so read the touchdown states rather than the summary line.

only `/app/controller.py` gets collected. the standard library is there when i run it, numpy is `2.2.1` and scipy is `1.15.1`, and nothing else, so do not build on anything you pip installed. `from lander import sim` works too if you want the plant on hand at run time. each episode gets 45 seconds of wall clock including your import, and going over just fails that episode.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
