# Final verification — October 11, 2026

The app, documentation, and approved 60-second video are prepared for submission. The portal submission has not been sent, and no organizer message has been sent.

## Checks completed

- 26 backend tests and 9 frontend tests pass; production compilation passes.
- Playwright browser workflow passes at 1440 × 1000 with 2× pixel density: drawing, generation state, all three force controls, failed-edit retry, refresh restoration, and reset. The browser test stubs model responses; genuine inference is verified separately.
- The browser restored the existing user world through the real backend with no page errors. Create and evolve screenshots were inspected. The user world was not changed.
- Native Apple M1 Pro / 16 GB inference completed offline at 512 × 512, 20 steps, float16 on MPS. Two initial landscapes took 47.88 and 32.80 seconds; cumulative Time, Water, and Light took 23.83, 21.84, and 20.81 seconds. No memory or precision failures occurred in this run.
- The API committed revisions 1 → 2 → 3 → 4 and checked exact pixel preservation outside each expanded blend mask. Old image revisions were rejected. The test used a separate fixture world.
- Model revisions and dependencies remain pinned. Safety checking stays enabled, with one resident pipeline and one inference job at a time.
- The approved video is 60 seconds, 1920 × 1080, 30 fps, H.264/AAC. Its generation waits and reconstructed second-slide sketch are labeled. The genuine AI artwork was not regenerated for that sketch revision.

## Limitations

Composition and force interpretation remain approximate. Time produced more vegetation and Light produced golden illumination in the final native run; Water also introduced an unexpected tower. Ground tree canopies remain inconsistent. See [model comparison](model-comparison.md) and [Metal measurements](assets/metal-measurements.json).

The video is a captioned results reel rather than a browser interaction recording. Browser behavior and native inference were verified separately.

The published schedule and rules still disagree between EDT and AoE. Planning uses the earlier deadline: Monday, October 12 at 05:59 Madrid time. Organizer confirmation and final portal submission remain outstanding.

## Publishing

Source and submission assets are published through the checkout in /private/tmp/magical-landscape-publish. Runtime caches, model weights, environment files, and private transient worlds are excluded. The approved showcase is the public video asset.
