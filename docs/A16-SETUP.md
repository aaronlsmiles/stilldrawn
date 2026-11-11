# A16.4's answers: Midjourney's image-to-video through its web app

The operator's own record of what A16.4 leaves to be found out after registration. It was made on
2026-11-11 (UTC), before any scout job. No panel of the dataset was uploaded to Midjourney, and no
Midjourney video of a benchmark panel exists.

## How the answers were found

- **Test image.** A plain black-and-white ink-style drawing made by code for this check (a boat on
  the sea, a dotted sun, a cloud, three gulls), 1344 × 768. It is not in the dataset and is clear
  for public posting. sha256 `ba65d44cb83a204e781133bc55a260c622c110ece4b19e693e68169bcbdccbbd`.
- **Two jobs, run by hand by Aaron in Midjourney's web app** (A16.3.1), on his Standard plan, with
  the same image as the starting frame, the same prompt and the same settings: the frozen BURST
  prompt of `harness/motion-prompts.md`, followed by ` --seed 20260812`; video resolution HD;
  video batch size 1; speed Fast; Motion High (see answer 2); no ending frame, Loop unticked.
- **Job ids.** First job `bb08c28a-f3a1-4697-8b49-1f85374ebe30` (its job page's age and its
  download time put it at about 13:52 UTC); second job `0937cf81-fe17-46b4-ad91-6689a0800901`
  (about 14:20 UTC, on the same basis).
- **Fields read.** In the web app: the settings panel (Video resolution, Video batch size, Speed)
  and the bar that appears when an image is loaded as the starting frame (Animate, End Frame with
  its Loop box, Motion). On each job page: the prompt as stored, and the parameters listed under
  it, both read by script from the page as well as from the screenshot. On each downloaded file:
  its streams, frame size, frame count and frame rate.
- **Files, kept privately and named here by sha256.** Neither video is measured.

| File | What it is | sha256 |
|---|---|---|
| `seed-1.mp4` | the first job's video, downloaded with the raw-video option | `28f25c4a5b012c99c54bda580470058ee7355017caa174054746740a6ab75f59` |
| `seed-2.mp4` | the second job's video, the same download | `a6ae599e029408eaf5d85118b5659f0335ee6f691da5d90f17708a5754d55736` |
| screenshot | the settings panel | `d9c9fe0b0e893d1b9013e232adc08dfb21caaf9a2bff0137b478329467d381c9` |
| screenshot | the bar with the test image loaded and no prompt, Motion showing Low selected (time of capture not recorded) | `047b8efb648025a276562a34997e934054ed5b4d6ccc870b1d6857ac4a64b053` |
| screenshot | the bar with the prompt pasted, before the second job was submitted, Motion showing High selected | `99f25833ecb6daf9793c4a6602a5082caa713a07ad022d0cb2c63ebf2645c72b` |
| screenshot | the first job's page | `3823e7b7c7c7d326e03cbfa6435a18449ece018a8bb90ce21fc1933a58d91462` |
| screenshot | the second job's page | `ecbe95d300e5f0b7fff59fd90231cfa2d947e1b48a8c73f967a04cdaf2a9fc28` |

## The answers

1. **Seed (A16.4.1): accepted, not honoured.** The interface took ` --seed 20260812`, and both job
   pages list `--seed 20260812`. The two videos have 125 decoded frames each, and no frame of the
   first has the md5 of the same frame of the second (0 of 125 equal). Under A16.4.1 the seed is
   not honoured: no seed would be sent, the manifest would record `seed: null` with this reason,
   and each cell would be one draw.
2. **Motion setting (A16.4.2): the default is "Low".** The bar offers Motion "Low" and "High".
   Aaron states that, with the test image loaded and nothing else touched, "Low" was selected. A
   screenshot (time of capture not recorded) shows the bar with the test image loaded, no prompt,
   and Low selected. Midjourney's help page, read the same day, also names Low Motion as the
   default. Aaron then switched the setting to "High", and both jobs ran at High: their pages list
   `--motion high`. That was a departure from the instruction to leave the setting alone. It does
   not touch answer 1, which compares two jobs with the same settings. A16.4.2 pins the default as
   shown on the day of the scout's first job; no scout job was run (answer 5).
3. **End frame (A16.4.3): offered by the interface; not tried with an image.** The bar has an
   "End Frame" section ("How the animation ends") with a "Loop" box.
4. **Resolution (A16.4.4): HD is available.** The settings panel offers Video resolution "SD" and
   "HD" on the Standard plan. Both jobs list `--res HD`; both files are 1264 × 720.
5. **The frozen prompt, verbatim (A16.4.5): no.** The prompt as each job page stores it, compared
   with the frozen prompt by script, differs in one character: the frozen prompt's long dash
   (U+2014) is stored as a hyphen (U+002D), at the 198th of its 359 characters ("every frame -
   line weight"). The bar showed the long dash before the second job was submitted. The seed
   parameter was removed from the text and listed among the parameters. Each of the six frozen
   prompts A16 would use (FLINT, BURST and the four ladder levels) has one such dash. Under
   A16.4.5 nothing runs.
6. **Videos per job (A16.4.6): one, when set.** Video batch size offers 1, 2 and 4. It was set to
   1, and each job returned one video.

## Also seen, and recorded as seen

- **Length.** Both job pages list `--duration 5.2s`, and both files hold 125 frames at 24 frames a
  second (5.208 s). Whether the interface offers a 5 s length was not looked for. A16.5.1's check
  accepts a file that lasts 5 s within one frame, so the job log would record a file of this
  length as a failed job (A16.5.4).
- **Other parameters listed on both job pages:** `--ar 128:73`.
- **Model version.** The job page is headed "Video" and shows no version label for the video
  model. The settings panel's Model section shows Version 8.2 and a Standard/HD toggle on HD;
  nothing on the job page ties either to the video.
- **Audio.** Neither file has an audio stream.
- **GPU time (A16.11).** Fast time read 15h before and 14h 47m after (Aaron's reading): about 13
  minutes for the two jobs, if nothing else used Fast time in between. At that rate about 60 jobs
  would need about 6.5 hours, within what was left (measured at Motion High only).

## What follows

A16.4.5 is not met, so no scout job and no arm job is run on Midjourney, and none was. Once these
answers are entered (`harness/mj_log.py setup`), the job log refuses to print a job
(`harness/mj_log.py next`). Aaron was told on 2026-11-11 and ruled the same day that Midjourney
stops here for this study.
