# Reviewing access changes on AWS

Read this when a plan touches IAM roles, users or policies, trust relationships, or
the resource policies on buckets, queues, topics and keys. Access changes are the
part of a plan where an in-place `~` update does the most damage while looking the
least alarming, and where an agent is most likely to have made something work by
making it wider.

## Read the policy, not the plan line

The plan line says a policy changes. The document is what grants access. Find it in
one of three places:

- In the code, usually an `aws_iam_policy_document` data source or a `jsonencode()`
  expression. This is the only source when the plan shows `(known after apply)`.
- In the console plan, where recent Terraform versions print a JSON-aware diff of the
  policy string.
- Rendered: `terraform console`, then `data.aws_iam_policy_document.<name>.json`,
  once its inputs are known.

AWS can check a document without applying it. Both commands are read-only but need
credentials:

```bash
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY \
  --policy-document file://policy.json
aws accessanalyzer check-no-new-access --policy-type IDENTITY_POLICY \
  --existing-policy-document file://before.json --new-policy-document file://after.json
```

The first reports errors, security warnings and overly broad statements. The second
answers the question a reviewer actually has, whether this change grants anything
new, and returns `FAIL` when it does. Use `RESOURCE_POLICY` for bucket, queue and key
policies.

## Wildcards

| Pattern | Why it matters |
|---|---|
| `"Action": "*"` or `"s3:*"` | Grants every current and future action of the service, including deleting buckets and rewriting their policies |
| `"Resource": "*"` on data actions | `s3:GetObject` on `*` reads every bucket the account can reach, not the one the job needs |
| `"Principal": "*"` or `{"AWS": "*"}` in a resource policy | Anyone, including anonymous callers for S3 unless Block Public Access stops it. Acceptable only with a condition that narrows it, such as `aws:PrincipalOrgID` or `aws:SourceVpce` |
| `NotAction` or `NotResource` with `Allow` | Grants everything except the list, including services added later |
| `iam:PassRole` on `*` | Lets the holder hand any role, including an admin one, to a service they control |
| `iam:PutRolePolicy`, `iam:AttachRolePolicy`, `iam:CreatePolicyVersion` on `*` | Lets the holder grant themselves anything; an escalation path, not a permission |

A common agent pattern: a job fails with access denied, the agent widens the action
or resource to `*`, the job passes, and the pull request says "fix permissions". The
narrow fix is usually the correct ARN form.

## Attach it to the right ARN

S3 permissions split between the bucket and the objects in it. `s3:ListBucket` needs
`arn:aws:s3:::my-bucket`; `s3:GetObject` and `s3:PutObject` need
`arn:aws:s3:::my-bucket/*`. A statement with the wrong form grants nothing, and the
usual "fix" is the wildcard above. Check the same way for prefixes: a job that reads
`raw/orders/` does not need `my-bucket/*`.

The resource that carries a policy matters as much as its text:

- `aws_iam_policy_attachment` is exclusive across the whole account. It detaches the
  policy from every role, user and group not listed in it, including ones another
  stack manages. Use `aws_iam_role_policy_attachment` per role.
- `aws_s3_bucket_policy` owns the entire bucket policy. Two resources, or two stacks,
  writing a policy for the same bucket overwrite each other on every apply, and the
  plan shows a permanent change. The same holds for `aws_sqs_queue_policy`.
- `managed_policy_arns` and `inline_policy` on `aws_iam_role` are exclusive too, and
  remove attachments made elsewhere.

## Trust policies

A role's trust policy decides who can become the role, which is often wider than
what the role can do.

- `{"AWS": "arn:aws:iam::111122223333:root"}` does not mean the root user. It
  trusts every principal in that account that has permission to call
  `sts:AssumeRole` on the role. For another account, that is a decision about the
  whole account.
- A vendor's cross-account role, such as the one a SaaS data platform assumes into
  your account, needs an `sts:ExternalId` condition with the value the vendor issued.
- An OIDC trust for CI, such as GitHub Actions or a cluster's service accounts, must
  condition on the subject. `token.actions.githubusercontent.com:sub` set to
  `repo:my-org/*` lets every repository in the organisation assume the role. Pin it
  to the repository and, for a deploy role, the branch or environment.
- A service principal, for example `s3.amazonaws.com` delivering notifications to a
  queue or `sns.amazonaws.com` publishing to one, needs `aws:SourceArn` or
  `aws:SourceAccount`. Without it, any bucket or topic in any account can use the
  service to write to your queue.

## Code buckets are execution rights

In a data platform, several buckets hold code rather than data: the DAG folder an
Airflow environment syncs from, cluster init scripts, job wheels and notebooks
copied to S3. Write access to one of them is the ability to run code as whatever
role executes it, which is usually a broad one. Review a grant of `s3:PutObject` on
such a bucket as a grant of that role, and keep the writers to the deployment
pipeline.

## Bucket settings that travel with access

- **Block Public Access** (`aws_s3_bucket_public_access_block`) should stay on for
  every data bucket. A change turning any of its four flags off is an access change
  even when no policy changed.
- **Transport.** A bucket policy statement denying requests where
  `aws:SecureTransport` is `false` is the usual baseline; removing it is a finding.
- **Encryption with KMS.** Reading an object encrypted with a customer key needs
  `kms:Decrypt` on that key as well as S3 permission, and the key policy must allow
  it. When a job breaks after encryption changes, the fix is on the key, not a wider
  S3 grant.

## Saying it in plain language

Restate each access change as who gains or loses what on which resource: "the role
Airflow tasks run as can now delete objects under `curated/` in the analytics bucket".
If that sentence cannot be written because the policy is not visible in the plan,
say so, and do not approve on the resource name alone.
