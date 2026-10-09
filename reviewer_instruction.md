Software Task Review Rubric: Project Kepler

Score each item Pass / Fail with a one-line reason. Decision rule at the bottom.

A. Fit for Project Kepler (gates: any Fail = send back)

In-scope software. Real engineering work in a covered subdomain (algorithms, systems, databases, data engineering, frontend, languages), not a competitive-programming exercise, tutorial build, or toy CRUD app.

Verifiable. Correctness checked by a deterministic program that passes iff the container ends in an acceptable state. Behaviour is graded, not style, architecture, or approach.

Well-specified. Instruction fully describes what verification checks (interfaces, file paths, output formats, performance thresholds, tolerances); a competent engineer could pass from the prompt alone.

Solvable. A real solve.sh exists, passes all tests, uses pinned and accessible deps, and genuinely implements the work rather than shipping precomputed outputs or stubbing the hard part.

Agentic and reproducible. Needs multi-step terminal work (read the codebase, run it, reproduce the failure, iterate); deterministic across runs, with no flaky timing, port, or ordering dependence; the answer isn't embedded in any file the agent can read.

B. Interesting

Novel, not cookbook. Can't be solved by recalling a standard pattern and applying a known library recipe; rewards a real combination of skills.

Essential difficulty. Challenge is in the engineering reasoning, not boilerplate, dependency wrangling, API trivia, or fighting the environment.

Real stakes. Resembles work a practitioner would actually be paid to do: a genuine bug in a real system, a migration, a performance problem, an integration under constraints.

C. Divergence

Discriminating point. A specific step where a competent solution and a naive one part ways, such as a concurrency invariant, an edge case in the data, a complexity boundary, or behaviour under load. Name it.

Legible failure. Failures happen at that point and are diagnosable from the trajectory, not from flaky tests, timeouts, or environment noise.

No degenerate shortcut. Can't be collapsed by hardcoding to the tests, brute force, weakening or disabling the checks, or otherwise exploiting the verifier instead of solving the problem.

Please leave feedback so the contributor can make corrections and send the tasks back.