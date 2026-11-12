# Contributing

## Real browser checks

The browser suite uses a real local server and CadQuery. With Node.js 22 or newer, install the locked development dependencies and Chromium:

```bash
npm ci --ignore-scripts
npx playwright install chromium
npm run test:browser
```

On Linux, `npx playwright install --with-deps chromium` installs Chromium system libraries as well. CI uses that route. The suite starts its own server on `127.0.0.1:8765`; stop another development server on that port first. Test jobs and reports are written beneath ignored `qa-output/playwright/`. No physical printer, native slicer, LLM account or API key is used.

Desktop and mobile browser projects check real CAD creation/downloads, profile evidence, shipping cost uncertainty, saved outcomes and failed-job history. `npm run test:browser:list` lists tests without launching a browser. DOM/controller tests and the real browser suite provide different evidence; report which one you actually ran.

Thanks for helping improve 3D Printer Agent. Bug reports, reproducible fixes, accessibility improvements, and documentation are welcome. You may write issues and pull requests in Korean or English.

Start with the [README](README.md), [product roadmap](docs/PRODUCT_ROADMAP.md), and [verification record](docs/VERIFICATION.md). They distinguish implemented features from plans and from hardware that has actually been tested.

## Development setup

Use Python 3.12 in a virtual environment. From the repository root on macOS or Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m print_agent
```

On Windows PowerShell, you can run the environment's interpreter directly:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m print_agent
```

Open `http://127.0.0.1:8765`. The template workflow needs neither an LLM API key nor a printer. Bambu Studio and an LLM server are optional integration targets; configure them only when testing those integrations. Installation instructions are not evidence that every operating system has passed validation.

## Run the relevant checks

The Python suite uses the standard library's `unittest` runner:

```bash
python -m unittest discover -v
```

The UI controller checks need Node.js and no additional Node packages:

```bash
node --check print_agent/static/app.js
node tests/test_ui_state.cjs
```

These tests use temporary files and synthetic slicer/provider responses. They do not require a real printer, Bambu account, or paid LLM credentials. A controller test using DOM doubles is different from a browser test. Report native slicer, browser, live-provider, and physical-print checks separately.

For a behavior change, add a focused regression test that fails for the reported problem. Documentation-only changes generally need link and command review rather than new tests. See the repository's workflows for checks required by CI.

## Make a reviewable change

Work on a branch or fork and keep the change focused on one problem. Explain the user-visible problem, the resulting behavior, and what you actually tested. Include the operating system and relevant versions when an integration is involved. Use the [pull request template](.github/pull_request_template.md) and describe any checks you could not run.

Preserve these project behaviors:

- Keep user requests and provider output within typed tool inputs. Do not execute arbitrary code returned by an LLM.
- Keep CAD validation, slicing, printer connection, and physical output as separate states. A user-reported success remains a user report.
- Keep supplied source metadata distinct from independently checked provenance. Unknown settings, compatibility, shipping costs, or measurements must remain unknown until evidence is available.
- Preserve original inputs and make generated artifacts traceable to parameters and settings. An earlier result must not appear to be the result of a failed new request.
- Keep the local application bound to loopback and retain its request-origin and session checks. Changes to remote access or physical printer actions need an explicit design and integration evidence.

When adding a CAD template, document units, editable dimensions, geometric constraints, and intended use. Check exported files and invalid inputs. When adding a profile or integration, record its applicable hardware/software conditions and the source of each supplied setting; synthetic test numbers are not manufacturer recommendations.

## Data and licensing

Do not commit API keys, printer access codes, account exports, session tokens, personal file paths, or users' print history. Local `.env`, `data/`, databases, and `qa-output/` are ignored by the repository; custom data directories need the same care. Use small, synthetic or anonymized fixtures and review screenshots and logs before attaching them.

Only contribute code, models, and documentation you have permission to share. Record attribution and applicable terms for third-party material; a model being downloadable does not establish permission to redistribute it here. Project contributions are provided under the repository's [MIT license](LICENSE). Third-party dependencies and imported assets retain their own licenses.

For security findings, follow [SECURITY.md](SECURITY.md) before posting technical details publicly.
