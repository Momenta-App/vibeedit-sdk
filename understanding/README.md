# VibeEdit for agents

Start here: https://vibeedit.com/.well-known/vibeedit.json

Public source and agent entry point:
https://github.com/Momenta-App/vibeedit-sdk/tree/main/understanding
The repository contains these instructions, the setup CLI, its tests and the
config schema. VibeEdit serves matching public copies and the API/SDK downloads.

VibeEdit provides six understanding APIs through one existing account system,
project-scoped keys and separately metered prepaid analysis. This page, the JSON
manifest, the public setup CLI and the SDK require no login to read/download.
Creating or accessing a user's account requires that user's authorization and
real email verification. There is no public credential or administrator token.

## Set up without a browser download

Use Python 3.11+ on macOS or Linux. Download and inspect the public setup source:

```sh
curl --fail --show-error --location https://vibeedit.com/agent-setup.py -o vibeedit_setup.py
python3 vibeedit_setup.py discover
python3 vibeedit_setup.py --help
```

The manifest publishes the setup file's SHA-256 and the SDK archive's SHA-256.
Verify the downloaded bytes before execution using your normal checksum tool.
Do not pipe remote source directly into a shell. Respect your agent's network,
file-write, download and code-execution approval controls; this workflow does not
waive them. If a particular action is denied, stop that action and explain it.

After the user authorizes signing in with their email:

```sh
python3 vibeedit_setup.py request-code --email USER_EMAIL --state /private/path/setup.json
python3 vibeedit_setup.py verify-code --state /private/path/setup.json
python3 vibeedit_setup.py accounts --state /private/path/setup.json
python3 vibeedit_setup.py create-key --state /private/path/setup.json --project my-project --config /private/path/vibeedit.json
python3 vibeedit_setup.py check --config /private/path/vibeedit.json
```

Replace USER_EMAIL and the paths. `request-code` signs in to an existing account
by default. Add `--signup` only when the user requested a new account and has
accepted the applicable https://vibeedit.com/terms and
https://vibeedit.com/privacy requirements. Never accept agreements for a user
without the authorization required by your tools.

`verify-code` prompts privately. An agent with authorized access to the delivered
code can use `--code-stdin` and provide it through standard input. Never pass a
code as a command-line argument, print it, or assume it from a fixture. Otherwise
ask the user for the code or let them enter it. This is the normal human identity
step; config saving and capabilities checks do not require browser clicks.

One account is selected automatically. With multiple accounts, run `accounts`,
then supply `--account ACCOUNT_ID` to `create-key`. The existing account owns the
balance and jobs. Do not create parallel accounts to get around an access error.

The default key has `video`, `faces` and `speakers` service grants, covering the
six services below, with only `read` and `download` operations. Billing management
is off. No upload, analysis, checkout or automatic payment begins during setup.
Supply `--services` and `--access` only for grants the user approved. Read access
is required to verify the issued key. For example, adding `--access read download
upload submit cancel` enables processing operations; it does not authorize their
use without an approved quote and maximum. `--billing-access` grants credit
management only when the user specifically authorized it; it never buys credit.

The CLI writes the config directly to the chosen local path with mode 600 and
checks its account/project through the production API. It does not invoke the
browser's Download config action. The temporary setup state also uses mode 600;
it contains a short-lived login token until the scoped config is safely saved,
then clears that token. No refresh token is retained. Never put these private
files in a repository, public chat, telemetry or support message. On other
platforms, implement the HTTP flow below using equivalent private storage.

## Use the SDK with that config

```sh
curl --fail --show-error --location https://vibeedit.com/headless/skill.zip -o vibeedit-sdk.zip
unzip vibeedit-sdk.zip
cd myrograph-headless
python3 myrograph.py --config /private/path/vibeedit.json capabilities --service speakers
```

The archive also includes this setup CLI as `vibeedit_setup.py` and these
instructions as `AGENT_SETUP.md`. Read its `SKILL.md` before analysis. Python
imports, MYROGRAPH environment variables and versioned schema identifiers retain
their existing names for compatibility. An existing SDK job/state/config must
keep its original API origin when resuming; use this new config for new work.

| Service | Capability route | SDK service |
|---|---|---|
| Words & Speakers | `/v1/voices/capabilities` | `speakers` |
| Face Identity | `/v1/faces/capabilities` | `faces` |
| Visible Speaker | `/v1/active-speakers/capabilities` | `active-speakers` |
| Voice Identity | `/v1/voice-identity/capabilities` | `voice-identity` |
| Words to People & Characters | `/v1/characters/capabilities` | `characters` |
| Visual Understanding | `/v1/video/capabilities` | `visual` |

Use https://vibeedit.com/docs for dependency, source-clock, uncertainty, artifact,
retention and review contracts. A link between identities is not proof of speech
or a verified name. Keep unknown/unresolved evidence explicit.

## Check media before paid analysis

Account setup and successful capability requests do not qualify a media file.
Before uploading a six-service source, inspect the actual video stream and its
packet timestamps. Face Identity currently requires one H.264/HEVC video stream,
constant frame rate, unique presentation timestamps starting at zero, and a
supported pixel format (`yuv420p` or `yuv420p10le`). Its limit is 120 FPS and four
hours. Use current service limits when they change. Audio and video clocks must
remain aligned for the linking services.

With a separately installed FFmpeg/ffprobe, this read-only check shows stream
metadata; inspect packet PTS as well when the clock is uncertain:

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt,r_frame_rate,avg_frame_rate,time_base,start_pts,start_time,duration -of json SOURCE.mp4
ffprobe -v error -select_streams v:0 -show_packets -show_entries packet=pts -of csv=p=0 SOURCE.mp4
```

A container `start_time` of zero does not establish a zero-origin **video**
clock. Likewise, matching average and nominal frame rates do not prove a uniform
packet clock. Website demonstration videos are presentation assets; they are
not promised to satisfy every analysis input contract. Validate your selected
bytes before paid admission. The public capability projection currently omits
these clock requirements, and a held public status may require support to learn
the specific qualification failure.

If normalization is needed, keep the original, create a separate file, preserve
audio/video alignment and verify the new clock. Use its new hash and truthful
full duration for new quotes and a newly authorized operation. Never replace
source bytes or parents inside an existing job/state. A qualification failure
may still incur infrastructure cost; retain its hold until the original usage
is reconciled. Do not retry held work or buy more credit automatically.

## Direct HTTP onboarding contract

All service requests use `https://vibeedit.com`. The documented account provider
is the existing authority returned by `GET /v1/video/auth`, currently
`https://cnvibkgxcaaohnxbsxoi.supabase.co`. That response contains the public
`publishableKey`; it is not an account credential. Send it as `apikey` for the
provider's normal email endpoints. Do not use a Supabase service-role key.

1. POST `{ "email": "USER_EMAIL", "create_user": false }` to the provider's
   `/auth/v1/otp?redirect_to=https%3A%2F%2Fvibeedit.com%2Fauth%2Fcallback` with
   `Content-Type: application/json` and `apikey`. Use true only for authorized
   signup. Honor the resend cooldown and HTTP 429; never loop email requests.
2. POST `{ "email": "USER_EMAIL", "token": "USER_SUPPLIED_CODE", "type": "email" }`
   to `/auth/v1/verify` with the same public apikey. Keep its access token in
   private transient state. Validate it using GET `/auth/v1/user` with apikey and
   `Authorization: Bearer ACCESS_TOKEN`.
3. GET `https://vibeedit.com/v1/video/accounts` with that bearer access token.
   The current response is `{ "accounts": [{ "accountId": "ACCOUNT_ID", "name": "..." }] }`.
   Older compatibility replies use `id`. The CLI accepts both and prints `id`.
4. Before key admission, durably record one random Idempotency-Key and this exact
   body in private state. POST it to `/v1/video/keys` with the login bearer token,
   Content-Type JSON and that Idempotency-Key:

```json
{
  "accountId": "ACCOUNT_ID",
  "projectIds": ["my-project"],
  "customerServices": ["video", "faces", "speakers"],
  "customerAccess": ["read", "download"],
  "customerBillingAccess": false
}
```

5. HTTP 201 returns the scoped `apiKey`, `organizationId`, mode and scopes.
   Save `{ "apiUrl": "https://vibeedit.com", "apiKey": "ISSUED_KEY",
   "organizationId": "ACCOUNT_ID", "projectId": "my-project" }` in a private
   file. Its public shape is https://vibeedit.com/config.schema.json.
6. Verify GET `/v1/customer/context?service=video&projectId=my-project&access=read`
   and capability routes with `Authorization: Bearer ISSUED_KEY`,
   `X-Project-Id: my-project` and `X-Organization-Id: ACCOUNT_ID`. Confirm returned
   identity matches the selection; remove the broader temporary login token.

If key creation times out or an acknowledgement is uncertain, retain that exact
identity/body/selection. Retry the same request; never mint a replacement merely
to recover. Changed scopes under the same identity return 409. The CLI enforces
this and serializes processes using the same state file. Existing configs are
never overwritten. Repeating a completed create-key command reuses its saved
acknowledgement. If login expires, request/verify a new code using the same state
and email while preserving the pending key identity.

## Billing, recovery and revocation

Check GET `/v1/video/billing` with the scoped key before assuming funds or mode.
Analysis credit is optional, separately metered and never included in a desktop
subscription. Get a current quote, obtain user approval for the operation and its
maximum, then submit with one durable identity. Preserve original jobs/holds on
unknown outcomes. A checkout return does not grant credit; only signed payment
confirmation does. Do not enter real payment details in TEST mode or fabricate
payment webhooks. Browser payment and security prompts still follow your tool's
approval rules. The default setup key has no funding authority; issue a separately
authorized key with `--billing-access` when the user asked to manage credit.

### Prepare credit through the API

```sh
python3 vibeedit_setup.py balance --config /private/path/vibeedit.json
python3 vibeedit_setup.py checkout --config /private/path/vibeedit.json --amount-usd 25 --state /private/path/checkout.json
```

Amounts are $5, $10 or $25 USD; choose only what the user authorized. This command
prepares one Stripe Checkout session and **does not pay**. It records the amount,
account, wallet mode and idempotency identity before the request. It saves the
private `checkoutUrl` in the mode-600 state, not standard output. Open that URL
from the private file with the agent's approved browser, verify Stripe's account,
mode and amount, and follow the user's and tool's payment approval requirements.
Do not print the private URL into public logs. Payment is a human approval step
when required by your tools; the CLI does not bypass it or enter saved cards.

After returning to VibeEdit, run `balance` again and check signed confirmation
and credit history. A return URL alone is not proof of payment or credit. Keep
the original checkout state on an uncertain acknowledgement; repeat the exact
command to recover that session. Changing amount, account, project or mode under
that identity is refused. Do not create another purchase merely to recover.

The direct contract is GET `/v1/video/billing` and POST
`/v1/video/billing/checkout` with `{ "amountUsd": 25 }`, API-key/project/account
headers and one durable `Idempotency-Key`. A successful checkout response contains
`url`, `amountUsd`, `currency` and `mode`; an internal Stripe session ID is not
required in the public response. Credit history is GET `/v1/video/billing/history`
with funding-management access. See https://vibeedit.com/setup/openapi.json for
the account and funding API reference.

### Approved TEST access

TEST access is a separate restricted operator-approved program, not a free
public analysis grant. The public client cannot approve itself, change its
ceiling or renew an expired campaign. Use it only when the operator authorized
that exact verified email. This calls the existing isolated TEST-account service:

```sh
python3 vibeedit_setup.py request-code --email APPROVED_TEST_EMAIL --state /private/path/test-setup.json
python3 vibeedit_setup.py verify-code --state /private/path/test-setup.json
python3 vibeedit_setup.py create-key --sandbox --state /private/path/test-setup.json --project my-test --config /private/path/test-vibeedit.json --access read download upload submit cancel library --billing-access
python3 vibeedit_setup.py balance --config /private/path/test-vibeedit.json
python3 vibeedit_setup.py checkout --require-test --config /private/path/test-vibeedit.json --amount-usd 25 --state /private/path/test-checkout.json
```

These processing/funding grants are broader than the default read-only key;
select them only for a user-authorized test. `--sandbox` calls POST
`/v1/video/sandbox/keys` with the ordinary verified login bearer, exact scope
body and durable idempotency identity, **without** accountId. It verifies the
returned account/project/mode before saving. The server enforces approved email,
campaign ceiling and expiry; repeat requests do not multiply the test allowance.
An approval failure needs an authorized operator, not another account or token.
Normal setup still uses `/v1/video/keys` and the user's selected existing account.

Check that the wallet reports `test` and Stripe visibly says Sandbox before using
the documented Stripe test card `4242 4242 4242 4242`, a future expiry and any
three-digit CVC. Test transactions move no real funds. Never use a real card to
test, and never put a test card into LIVE Checkout. `--require-test` refuses a
LIVE wallet before preparing checkout. See https://docs.stripe.com/testing.
TEST credit cannot become LIVE credit. Processing may still consume the approved
test campaign budget and real service resources; obtain fresh per-stage quotes
and a total approved cap before starting the six-service flow.

To revoke only the key in a config:

```sh
python3 vibeedit_setup.py revoke --config /private/path/vibeedit.json
```

Revocation blocks new API calls, not already issued signed links or accepted
cloud jobs. Troubleshoot at https://vibeedit.com/support without sharing secrets.
Myrograph compatibility endpoints remain online. VibeEdit Library is local-only,
requires no analysis account and is documented at https://vibeedit.com/docs/library.
