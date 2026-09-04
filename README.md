# GraphCheck Action

Run [GraphCheck](https://github.com/graphora/graphcheck) in GitHub Actions and keep the CLI's
result as the workflow result. This Action is a thin wrapper around `graphcheck run`; it adds no
checks or verdict logic of its own.

## Usage

```yaml
- uses: actions/checkout@v4
- uses: graphora/graphcheck-action@v1
  with:
    profile: ci
    uri: bolt://localhost:7687
    user: neo4j
    database: neo4j
    upload-artifacts: always
  env:
    NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
```

The Action installs the released `graphcheck==0.3.0` wheel by default. The pin makes otherwise
identical workflow runs reproducible. To choose another release, override it with an exact version:

```yaml
- uses: graphora/graphcheck-action@v1
  with:
    version: 0.3.0
    uri: bolt://localhost:7687
    user: neo4j
```

Set `version: ''` only when an earlier step has installed the desired `graphcheck` CLI on `PATH`,
for example when smoke-testing a source checkout.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `profile` | no | `ci` | Profile to use, and to generate when `profiles.yml` does not exist |
| `uri` | yes | - | Neo4j Bolt URI |
| `user` | yes | - | Neo4j username |
| `database` | no | `neo4j` | Neo4j database name |
| `fail-fast` | no | `false` | Pass `--fail-fast` to `graphcheck run` |
| `suite` | no | - | Pass `--suite <value>` when set |
| `concurrency` | no | - | Maximum workers; empty uses `graphcheck.yml`, then 0.3.0 defaults to `2` |
| `artifact-name` | no | `graphcheck-results` | Unique artifact name; suffix for matrices or repeated calls |
| `upload-artifacts` | no | `always` | Upload `always`, `on-failure`, or `never` |
| `version` | no | `0.3.0` | Exact PyPI version; empty uses a pre-installed CLI |

The generated profile refers to `password_env: NEO4J_PASSWORD`; it never writes the secret value.
An existing `profiles.yml` is used unchanged. With the pinned GraphCheck 0.3.0 release, omitting
`concurrency` runs two checks at a time unless `graphcheck.yml` explicitly chooses another limit.

## CLI contract

After setup, the Action constructs only the requested CLI flags and invokes:

```console
graphcheck run [--profile PROFILE] [--suite SUITE] [--fail-fast] [--concurrency N]
```

It captures that process code only long enough to upload/present the CLI outputs, then exits with
the same code. The exact value is also available as the `exit-code` Action output. Installation or
preparation failures that happen before the CLI can run resolve to code `3` rather than an empty
output:

| Exit | Meaning |
| --- | --- |
| `0` | All evaluated checks passed |
| `1` | An error-severity check failed or errored |
| `2` | Warning or incomplete evaluation |
| `3` | The run could not prepare or execute |

With the default `upload-artifacts: always`, the `graphcheck-results` workflow artifact contains
the three files produced by the CLI:

```text
results.json
summary.json
report.html
```

`on-failure` uploads them only for a nonzero CLI result; `never` disables upload. Workflow
annotations and the Step Summary present run/check information from `results.json`; the Step
Summary reads canonical coverage status from `summary.json`. Neither presentation changes
GraphCheck verdicts or the final exit code.

Artifact names must be unique across a workflow run. Include the matrix dimensions or environment
when the Action can run more than once:

```yaml
- uses: graphora/graphcheck-action@v1
  with:
    artifact-name: graphcheck-results-${{ matrix.environment }}-${{ matrix.os }}
    uri: ${{ matrix.uri }}
    user: neo4j
```

## Version tags

Use `graphora/graphcheck-action@v1` to follow compatible v1 releases. For immutable pinning, use a
full release tag such as `graphora/graphcheck-action@v1.0.1` or a commit SHA. Patch tags are never
moved; the `v1` major tag advances only after the corresponding release contract passes.

## License

Apache-2.0.
