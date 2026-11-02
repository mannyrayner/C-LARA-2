# Google word audio: selection, conversion and deployment

This release adds an **optional** Google provider for future word and inflected-form
recordings, a reversible batch conversion tool, and broader provider comparisons.
No existing dictionary is switched automatically. Sentence and spoken-feedback
audio continue using OpenAI.

## Try it after installation

1. As the dictionary owner, open **Settings → Word audio settings**. Choose a
   Google voice, confirm permission and Google project billing, then save. The
   first rollout requires the owner to be a site administrator, because it spends
   the host's configured Google project funds. Contributors can then use the
   dictionary's chosen provider through the normal picture and vocabulary flows.
2. Start with **Tools → Compare word audio providers**, one take, a random sample
   of 30 lexical items. Save ratings before revealing the methods; export CSV.
   Use homographs/expressions as separate challenge samples. Existing experiments
   and their saved ratings remain available.
3. Open **Tools → Convert word audio to Google**. Prepare an estimate and approve
   it to generate private replacement previews for the whole dictionary. Words,
   expressions and inflected forms are included; compatible repeated forms share
   a recording. The limit is 2,000 groups per batch.
4. Human recordings are always excluded. Listener-approved AI recordings and
   recordings already using the selected Google voice are excluded by default;
   two explicit checkboxes can include those groups.
5. At completion, listen and accept individual previews, or choose **Use all
   usable replacements**. Bulk acceptance does not mark pronunciation as reviewed.
   Failed items retain their earlier audio. A new batch estimates any remaining
   missing/nonmatching audio; there are no automatic paid retries.
6. **Restore earlier audio from this batch** restores unchanged replacements.
   Later edits, human recordings and withdrawals are protected. Earlier files
   remain stored. Switching the future provider back to OpenAI also leaves all
   existing recordings intact.

Default trial voices are provided for French, Swedish, English, German, Italian,
Icelandic, Japanese, Slovak, Spanish and Chinese. Icelandic uses Standard; no
nonexistent WaveNet voice is invented. **Load available Google voices** lists
supported WaveNet, Neural2, Standard and Chirp 3 HD voices for other app languages,
or alternative voices in these languages. Select a listed voice to use it in
production and in subsequent comparisons. Unsupported languages keep OpenAI or
human recordings. Google availability does not imply validated pronunciation.

The provider choice is frozen in picture requests and batch estimates. Changing
it requires fresh estimates or renewed picture-workflow consent. Google receives
only lexical text, with an explicit locale; it receives no images, meanings or
human recordings. Sentence processing still sends the material described in its
OpenAI consent. Google costs use character tariffs before free allowances/tax,
not duration. A personal OpenAI key does not pay Google charges. Existing C-LARA
payment-mode accounting remains in force; when personal OpenAI mode is selected,
Google charges still fall on the administrator-authorised host project.

## One-time additive schema preparation

Migration **0028_word_audio_settings** creates one preference table. It does not
rewrite dictionary content. The normal deployment controller intentionally
refuses migrations. Use the separate reviewed schema-preparation commit supplied
with the release, then the usual code-only Actions workflows for the feature
release. **The schema commit and feature commit are different hashes.**

Preparation reuses the installed controller, maintenance gate, drain, service
identities, static-file identity and health checks. SQLite is backed up and
verified before migration. On AWS, confirm the usual RDS recovery/backups first.
Failure rolls the code back and restarts the preceding release when possible;
it never reverses the additive migration. A recovery_required receipt requires
inspection before another attempt.

### Laptop (Cygwin, with the Windows runner listening)

Set `CLARA_GOOGLE_SCHEMA` to the exact schema commit supplied in the release
message; do not substitute the latest main commit. The last confirmed laptop
feature release was `9093cc5a3a5af464005a625c5dbc0334579f7cfc`.

```bash
cd /home/github/c-lara-2
git status --short
git rev-parse HEAD
```

Proceed only with a clean checkout at that expected release; if it differs,
report the actual hash rather than weakening the expected-commit check.

```bash
CLARA_GOOGLE_SCHEMA='87ef2df3d0127a434390188f12420227fa8b204b'
git fetch origin &&
git show "$CLARA_GOOGLE_SCHEMA":ops/community_deploy/prepare_word_audio_schema.py > ../clara-deploy/prepare_word_audio_schema.py &&
./.venv/Scripts/python.exe -E ../clara-deploy/prepare_word_audio_schema.py \
  --controller ../clara-deploy/bin/runner.py \
  --config ../clara-deploy/laptop.json \
  --expected 9093cc5a3a5af464005a625c5dbc0334579f7cfc \
  --commit "$CLARA_GOOGLE_SCHEMA"
```

Require `status: prepared`. Start a **new** “Install Community Dictionaries on
laptop” workflow on main in the deployment-control repository. Its request
expects the schema commit and installs the feature commit. Do not rerun a prior
workflow. Test settings, comparison, conversion, individual/bulk acceptance,
restoration, and creation of a new picture entry before AWS installation.

Existing working laptop user ADC needs no replacement. Never put ADC files in
Git or copy them to AWS. The provider ignores old GOOGLE_APPLICATION_CREDENTIALS
and GOOGLE_CREDENTIALS_JSON variables.

### AWS schema and feature installation

In the usual EC2 terminal:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
git status --short
git rev-parse HEAD
```

The last confirmed AWS release was
`e9c9c03209116f5145d51255fedb63d69840cc20`. If it differs, stop for reconciliation.
With a clean checkout and the exact schema commit from the release message:

```bash
CLARA_GOOGLE_SCHEMA='87ef2df3d0127a434390188f12420227fa8b204b'
umask 022
git fetch origin &&
git show "$CLARA_GOOGLE_SCHEMA":ops/community_deploy/prepare_word_audio_schema.py > /var/lib/clara-deploy/prepare_word_audio_schema.py &&
/usr/bin/python3 /var/lib/clara-deploy/prepare_word_audio_schema.py \
  --controller /opt/clara-deploy/runner.py \
  --config /etc/clara-deploy.json \
  --expected e9c9c03209116f5145d51255fedb63d69840cc20 \
  --commit "$CLARA_GOOGLE_SCHEMA"
```

Require `prepared`. Use **Accept laptop and deploy AWS** on main after accepting
the successful current laptop installation. The workflow installs the same
feature commit, expecting the prepared AWS schema commit. Confirm the health
endpoint's release and browse before enabling Google on a dictionary.

Google remains disabled by default on Linux. The application can be deployed and
browsed before Google federation is configured; ordinary OpenAI dictionaries keep
working. Do not enable a Google voice on AWS until the access check below passes.

## AWS Google authentication: federation, no downloaded key

The code accepts a reviewed, explicit AWS Workload Identity Federation
configuration using IMDSv2 and service-account impersonation. This is separate
from the GitHub deployment role. It does not reuse the previously compromised
project or credential, or copy the laptop's refresh token.

### 1. Identify the EC2 instance role (AWS CloudShell, read-only)

Use the AWS account/region/instance already used for deployment:

```bash
aws sts get-caller-identity --query Account --output text
aws ec2 describe-instances --region ap-southeast-2 \
  --instance-ids i-08e13bb4b0c3ecb15 \
  --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' --output text
```

Verify the expected AWS account. Take the final name in the instance-profile ARN
and inspect its role:

```bash
aws iam get-instance-profile --instance-profile-name 'PASTE_INSTANCE_PROFILE_NAME' \
  --query 'InstanceProfile.Roles[].{Name:RoleName,Arn:Arn}' --output json
```

Use that **EC2 role name**, not the deployment role. If no profile or more than
one unexpected result appears, resolve that before creating trust. Do not edit
or remove the instance's existing permissions.

### 2. Create narrowly scoped Google trust (Google Cloud Shell)

Sign in as the Google administrator for the existing
`community-dictionaries-tts` project. These commands create new resources named
`clara-aws`, `clara-ec2`, and `clara-tts`; if a resource already exists, inspect it
instead of overwriting it. Fill in the verified role name and account number.

```bash
CLARA_GOOGLE_PROJECT='community-dictionaries-tts'
CLARA_AWS_ACCOUNT='PASTE_VERIFIED_AWS_ACCOUNT_NUMBER'
CLARA_EC2_ROLE='PASTE_VERIFIED_EC2_ROLE_NAME'
CLARA_INSTANCE='i-08e13bb4b0c3ecb15'
CLARA_AWS_SUBJECT="arn:aws:sts::${CLARA_AWS_ACCOUNT}:assumed-role/${CLARA_EC2_ROLE}/${CLARA_INSTANCE}"
CLARA_GOOGLE_NUMBER="$(gcloud projects describe "$CLARA_GOOGLE_PROJECT" --format='value(projectNumber)')"
CLARA_GOOGLE_SERVICE="clara-tts@${CLARA_GOOGLE_PROJECT}.iam.gserviceaccount.com"
```

Enable the required services, create the service account, and grant use of the
billing/quota project. Ordinary synchronous Cloud TTS uses service-usage
permission; do not grant Editor or Owner for speech synthesis. The application
sets an explicit quota project, including during service-account impersonation.
Grant Service Usage Consumer to both the service account and the exact federated
EC2 principal: the latter authenticates the request to obtain the service-account
token, before the service account can be used.

```bash
gcloud services enable texttospeech.googleapis.com iam.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com --project="$CLARA_GOOGLE_PROJECT" &&
gcloud iam service-accounts create clara-tts --project="$CLARA_GOOGLE_PROJECT" \
  --display-name='Community Dictionaries lexical audio' &&
gcloud projects add-iam-policy-binding "$CLARA_GOOGLE_PROJECT" \
  --member="serviceAccount:$CLARA_GOOGLE_SERVICE" \
  --role=roles/serviceusage.serviceUsageConsumer &&
gcloud iam workload-identity-pools create clara-aws --location=global \
  --project="$CLARA_GOOGLE_PROJECT" --display-name='Community Dictionaries EC2' &&
gcloud iam workload-identity-pools providers create-aws clara-ec2 --location=global \
  --workload-identity-pool=clara-aws --project="$CLARA_GOOGLE_PROJECT" \
  --account-id="$CLARA_AWS_ACCOUNT" --attribute-mapping='google.subject=assertion.arn' \
  --attribute-condition="assertion.arn == '$CLARA_AWS_SUBJECT'" &&
gcloud projects add-iam-policy-binding "$CLARA_GOOGLE_PROJECT" \
  --member="principal://iam.googleapis.com/projects/$CLARA_GOOGLE_NUMBER/locations/global/workloadIdentityPools/clara-aws/subject/$CLARA_AWS_SUBJECT" \
  --role=roles/serviceusage.serviceUsageConsumer --condition=None &&
gcloud iam service-accounts add-iam-policy-binding "$CLARA_GOOGLE_SERVICE" \
  --project="$CLARA_GOOGLE_PROJECT" --role=roles/iam.workloadIdentityUser \
  --member="principal://iam.googleapis.com/projects/$CLARA_GOOGLE_NUMBER/locations/global/workloadIdentityPools/clara-aws/subject/$CLARA_AWS_SUBJECT" &&
gcloud iam workload-identity-pools create-cred-config \
  "projects/$CLARA_GOOGLE_NUMBER/locations/global/workloadIdentityPools/clara-aws/providers/clara-ec2" \
  --service-account="$CLARA_GOOGLE_SERVICE" --aws --enable-imdsv2 \
  --output-file=clara-google-wif.json
```

The condition admits the EC2 role session for this instance only. A moved/replaced
instance needs an explicit trust update. The JSON is a configuration, not a
private key; nevertheless keep it integrity-protected. Download it using Cloud
Shell's file download, then transfer it through the existing administrator
channel to `/var/lib/clara-deploy/clara-google-wif.json` on EC2. No credentials
need to be pasted into chat, a dictionary, or Git.

### 3. Configure and verify the application identity (EC2)

```bash
sudo install -o root -g www-data -m 640 \
  /var/lib/clara-deploy/clara-google-wif.json /etc/clara-google-wif.json
sudoedit /etc/clara2.env
```

Add or update these three lines, preserving unrelated settings:

```text
C_LARA_GOOGLE_TTS_ENABLED=1
C_LARA_GOOGLE_TTS_PROJECT=community-dictionaries-tts
C_LARA_GOOGLE_TTS_ADC_FILE=/etc/clara-google-wif.json
```

Check using the same identity and environment as the services:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}
clara_manage community_google_tts_check --username mannyrayner
clara_manage community_google_tts_check --username mannyrayner --contact-google
```

The second command refreshes credentials and lists voices, but synthesises no
speech. Require success before enabling a dictionary. A federation failure may
mean the instance role, trust condition, IMDSv2 availability or service-usage
permission differs from the configuration. The Google auth library can also use
AWS credential environment variables if present; they must not select a different
identity from the EC2 role. Do not remove credentials used by other application
services to fix this; inspect the bounded diagnostic first.

After the checks pass, and with background jobs idle:

```bash
sudo systemctl restart gunicorn-clara2 djangoq-clara2 project-understanding-worker
curl --fail --silent --show-error --connect-timeout 10 --max-time 20 \
  https://c-lara-2.c-lara.org/community-dictionaries/deployment-health/
```

Choose Google on a small dictionary first; confirm correct audio and Google
provenance, then annotate the larger language samples. No live Google requests
were made by the developer during implementation; real AWS federation and voice
quality require this deployment-side test.

References checked 2 November 2026:

- [Google supported voices](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types)
- [Google TTS pricing](https://cloud.google.com/text-to-speech/pricing)
- [TTS authentication](https://docs.cloud.google.com/text-to-speech/docs/authentication)
- [Quota-project permissions](https://docs.cloud.google.com/docs/quotas/set-quota-project)
- [AWS federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds)
- [Credential configuration with IMDSv2](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/create-cred-config)
