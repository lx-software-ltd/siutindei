# Category suggestions

Unknown imported category names are captured instead of failing the
organization, then enriched off the request path. Admins approve, map,
or reject each suggestion in the admin console.

Endpoint shapes live in `docs/api/admin.yaml` under
`/v1/admin/category-suggestions`.

## Capture

Resolution order for `category_name` is exact name, then an alias from
an approved or targeted suggestion, then a unique fuzzy match on the
English name and `name_translations` (case, whitespace, and punctuation
insensitive). Anything else is captured when `on_import_enabled` is
true. When that switch is false, an unknown name still fails the
import the way it does today.

Captured activities use the system category Pending categorisation
(`c1111111-1111-1111-1111-111111111199`, Chinese name 待分類). Public
search always excludes that category. Organization review adds the
blocker `pending_category`, so an organization cannot be approved
without force while an activity is still pending.

One suggestion exists per normalised name. A rejected suggestion with
no target reopens if the same name is imported again. A target on
approve, map, or reject-with-target is an alias for later imports.
Reject without a target leaves activities on the pending category.

Live imports enqueue enrichment when a suggestion is created or
reopened, or when its activity count crosses 5 or 25. Dry runs roll
the suggestion rows back and enqueue nothing.

## OpenRouter

In-VPC Lambdas call OpenRouter only through
`app.services.openrouter_client`, which uses the existing HTTP proxy
(`http_invoke`). The worker reads the named key `lxsoftware:siutindei`
from Secrets Manager and sends `Authorization`. The proxy does not
store or inject that key.

Requests set `usage.include`, app attribution (`siutindei`, title
"Siu Tin Dei", referer `https://siutindei.com`), and
`provider.data_collection=deny` unless the admin setting disables it.
The default model is `qwen/qwen3-30b-a3b` with fallback
`qwen/qwen-turbo`. Admins change the model on the settings singleton
without a redeploy.

The worker timeout is 120 seconds and the OpenRouter call is 90
seconds. The admin "test model" action is one attempt of about 15
seconds because API Gateway REST integrations time out at 29 seconds
and the admin Lambda timeout is 30 seconds.

Prompts redact email addresses and phone numbers. The model is asked
to prefer an existing category, otherwise a sub-category, with a
Traditional Chinese name.

## Settings

`category_suggestion_settings` is a single row. `on_import_enabled`
defaults to false and is the only capture switch. `auto_enrich_enabled`
defaults to true. Model slugs match `vendor/model` and are at most 128
characters. At most three fallbacks are stored. Evidence size is 5 to
50 items, default 25.

Only the admin group can read or change suggestions and settings.
