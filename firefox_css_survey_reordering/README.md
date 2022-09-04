# Info

Note: this folder's contents are for a Firefox-only tweak.

## Background

tl40data.com has a fixed order of the survey items. When entering data for the survey, you often have to jump around, because the medals in PoGo are grouped by platinum/gold/silver etc.

But what if we could make this order more convenient, i.e. match the order of medals in PoGo?

This folder enables doing that.  (Also, this is inspired by Stadium.gg/stats aborted replacement for tl40stats, which did per-user ordering based on known stats.)

## Files

- `gen_userContentcss.py`: Run this: to:
    - Input your most recent row of survey history
    - Will output CSS rules that will re-order the survey boxes
    - Then paste those rules into your `userContent.css` file.
- `gen_mapping_columns_to_order.py`: (Re)generates `survey_to_pogo_order_mapping.json` from `ids` and `medal_counts.json`.
- `ids`: List of element names from source code of the tl40data.com/new page.  Order, however, is from the survey history columns.
- `medal_counts.json`: Data about different medals' thresholds.  For non-medal stats, we just put 0s.
- `survey_to_pogo_order_mapping.json`: Generated mapping from survey element to order of stats in survey history.

## Usage

in about:config:
toolkit.legacyUserProfileCustomizations.stylesheets to True

in about:profiles Open folder for "Profile: default"

Create a folder named "chrome"

In that folder create "userContent.css"

```css
@-moz-document url("https://tl40data.com/new") {
    img { opacity: 0.05 !important; }
    body { color: purple }
    .mdl-card__floating-action-bar > .mdl-card__actions {
            background: none;
    }
    #main-panel .mdl-grid > #id_total_xp__card { order: -400; }
    #main-panel .mdl-grid > #id_trainer_level__card { order: -399; }
    #main-panel .mdl-grid > #id_pokedex_caught__card { order: -398; }
    ... [ a few dozen more lines from output of gen_userContent_css.py ]
}
```

After doing the above, in `about:profiles` click "Restart normally...".
