# Third-party sources and data terms

The MIT license covers this repository's own code. It does not relicense upstream
videos, frames, annotations, model weights or services.

- **EgoPlan**: https://github.com/ChenYi99/EgoPlan .
  Source checkout used during development: `1510afc12bc832b50d6285d83503ecbdca093bf4`.
  Its source code is published under BSD-3-Clause; consult its LICENSE and dataset
  instructions. This repository implements a separate evaluation pipeline and
  does not redistribute the EgoPlan model or copy its model implementation.
- **EgoPlan annotation mirror**: https://huggingface.co/datasets/lmms-lab/EgoPlan/tree/515f017faf0cdf42a25654a1bcd879c12277eff1 .
  This fixed snapshot supplied 3355 validation records, including 27 for P30_111.
  Access and reuse remain subject to the upstream datasets' conditions.
- **EPIC-KITCHENS-100 annotations**:
  https://github.com/epic-kitchens/epic-kitchens-100-annotations/tree/ea8b40457a400c3fffa1c7f406ef3dc169cc2522 .
  The annotation license is [CC BY-NC 4.0](https://github.com/epic-kitchens/epic-kitchens-100-annotations/blob/master/license.txt).
  Preserve attribution, provide the license, indicate derived changes, and respect
  the noncommercial condition. Derived changes here include question intervals,
  post-action frame selection, interaction merging, optical-flow candidate labels
  and an explicit human correction.
- **EPIC videos and extracted frames**: obtain and use under the official dataset's
  conditions: https://epic-kitchens.github.io/2024#downloads .
  A collaborator bundle is provided separately; possession of it does not remove
  the obligation to comply with upstream permissions and restrictions.
- **OpenAI / Codex**: services and tools are used through their documented interfaces.
  No credentials, model weights or subscription entitlement are distributed here.

Cite EgoPlan and EPIC-KITCHENS as requested by their upstream projects when
publishing research based on these data. This repository is an experimental
derivative, not an official EgoPlan or EPIC benchmark release.
