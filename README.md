# DeepCodeGraph 

DeepCodeGraph is an LLM agent that automatically generates diagrams from codebases, supporting PlantUML, Mermaid, Graphviz, and D2 formats. It can produce both structural (class-like) and behavioral (activity-like) diagrams and offers options for local or web-based rendering for PlantUML. It also supports incremental scanning to speed up analysis of previously processed repositories.

![Example image of DeepCodeGraph UML diagram.](https://raw.githubusercontent.com/rhochgraf21/DeepCodeGraph/main/examples/simple_oo_python.png)

## Installation

Install using pip:

```
pip install deepcodegraph
```

Installation from source:

```
git clone https://github.com/rhochgraf21/DeepCodeGraph/
pip install -e .
```

### Dependencies for Local Image Rendering
To generate images locally for the supported diagram types (instead of just the text source files), you'll need to install additional tools:

- **Mermaid CLI (mmdc):** For rendering Mermaid diagrams (.mmd files) to SVG/PNG.
  - Installation: `npm install -g @mermaid-js/mermaid-cli` (Requires Node.js).
  - More info: [Mermaid CLI Documentation](https://github.com/mermaid-js/mermaid-cli)

- **D2 CLI:** For rendering D2 diagrams (.d2 files) to SVG/PNG.
  - Installation: Follow instructions at [D2 Official Install Guide](https://d2lang.com/tour/install).

- **Graphviz (dot):** For rendering Graphviz diagrams (.dot files). The Python `graphviz` library (listed in `requirements.txt`) uses these tools.
  - Installation: Via system package managers (e.g., `sudo apt-get install graphviz`, `brew install graphviz`).
  - More info: [Graphviz Download Page](https://graphviz.org/download/)

- **PlantUML Local Rendering (Java and plantuml.jar):**
  - **Java Runtime Environment (JRE):** Java must be installed and the `java` executable must be in your system's PATH. OpenJDK or Oracle JDK are suitable.
  - **`plantuml.jar`:** Download `plantuml.jar` from the [PlantUML Official Website](https://plantuml.com/download).
    - Place it in a known location. The system will look for it by default at `/usr/local/bin/plantuml.jar`.
    - Alternatively, you can specify its location using the `PLANTUML_JAR` environment variable:
      `export PLANTUML_JAR=/path/to/your/plantuml.jar`

## Usage

The `codegraph` tool is designed to analyze your code repositories by generating dependency graphs or exporting the repository structure. 

Below are the details on how to use the available commands and options.

### Global Options

These options apply to all commands.

- `-h, --help`  
  Show a help message and exit.

- `-v, --verbose`  
  Increase verbosity. This flag can be used multiple times for more detailed output.

- `--api-key API_KEY`  
  Specify your LLM API key. Alternatively, set the `CODEGRAPH_API_KEY` environment variable, or the API key environment variable for your provider as found in [LiteLLM](https://docs.litellm.ai/docs/providers/).

- `--provider PROVIDER`  
  Choose the LLM provider. The default provider is `gemini`.

- `--model MODEL`  
  Specify the model to use with the provider. The default is `gemini-2.0-flash-exp`.

### Commands

DeepCodeGraph offers the following commands:

#### `graph` Command
Generates diagrams from a repository. Produces diagram source code and can render images locally if required tools are installed. Supports multiple diagram formats and types (class/activity). Can use an existing analysis database for incremental scanning.

##### Graph Command Options

- `--path PATH`: Local filesystem path to your repository. (Mutually exclusive with --github)
- `--github GITHUB_URL`: URL of the GitHub repository to analyze. (Mutually exclusive with --path)
- `--format DIAGRAM_FORMAT`: Specify the main diagram language/format.
  - Choices: `plantuml`, `mermaid`, `graphviz`, `d2`.
  - Default: `plantuml`.
- `--diagram-type TYPE`: Specify the type of diagram to generate.
  - Choices: `class`, `activity`.
  - Default: `class`.
  - Applies to all formats.
- `--image-format IMG_FORMAT`: Specify the output image format for local rendering.
  - Choices: `png`, `svg`. Default: `png`.
  - Requires corresponding local rendering tools (see Installation section).
- `--plantuml-service SERVICE`: For PlantUML diagrams, choose the rendering service.
  - Choices: `local`, `web`. Default: `local`.
  - `local` requires Java and `plantuml.jar` (see Installation section). `web` uses the public PlantUML server (PNG only for web).
- `--extensions EXT_LIST`: Comma-separated list of file extensions to scan. Default: `.py,.js,.java,.cpp,.c,.h`.
- `--output DIR`: Directory to save generated graphs. Default: Current directory (`./`).
- `--input-db FILEPATH.JSON`: Optional path to an existing DB JSON file to use for incremental scanning and caching. If provided and no relevant files have changed, graph generation might be skipped.

#### `export` Command
Export the repository’s structure to a JSON file (referred to as a "DB" file). This file can be used for incremental scans later.

##### Export Command Options

- `--path PATH`: **Required if not using `--github`.** Local filesystem path to your repository.
- `--github GITHUB_URL`: **Required if not using `--path`.** URL of the GitHub repository to analyze.
- `--extensions EXT_LIST`: Comma-separated list of file extensions to scan. Default: `.py,.js,.java,.cpp,.c,.h`.
- `--format EXPORT_FORMAT`: Export format. Default: `json`. (Note: This `--format` is for the `export` command, distinct from the `graph` command's diagram format).
- `--output FILE_PATH`: Output file path for the exported structure. **Required.**
- `--input-db FILEPATH.JSON`: Optional path to an existing DB JSON file. If provided, the export will update this DB by scanning only new or changed files relative to the state in the input DB. The output will be written to the file specified by `--output`.

### Incremental Scanning and Caching

DeepCodeGraph supports incremental scanning to optimize performance for repositories that have been previously analyzed. This feature works by:

1.  **Creating a Database (DB) File:** When you run the `export` command, DeepCodeGraph analyzes your repository and saves its structure (including file paths, code element details, and content hashes) into a JSON file. This JSON file acts as a "database" (DB) of your repository's state at that time.
    ```sh
    codegraph export --path /path/to/your-repo --output my_repo_db.json
    ```

2.  **Detecting Changes:** For each file, DeepCodeGraph calculates a content hash (SHA256). When you re-run a command with an existing DB file (using the `--input-db` option), DeepCodeGraph compares the current file hashes against the hashes stored in the DB.
    *   If a file's hash matches the one in the DB, it's considered unchanged, and its structure is loaded from the DB, skipping LLM analysis for that file.
    *   If a file's hash differs, or if the file is new (not present in the DB), it's (re-)analyzed by the LLM.
    *   Files present in the DB but not found in the current repository are considered deleted and are excluded from the new analysis.

3.  **Updating the DB (with `export`):** If you use `export` with `--input-db` and `--output` (they can be the same file), DeepCodeGraph performs an incremental scan and then saves the updated repository structure to the output file.
    ```sh
    # Update my_repo_db.json with any changes from the repository
    codegraph export --path /path/to/your-repo --input-db my_repo_db.json --output my_repo_db.json
    ```

4.  **Faster Graphing (with `graph`):** If you use `graph` with `--input-db`, DeepCodeGraph loads cached data for unchanged files and only performs LLM analysis on new or modified files.
    *   **No-Change Optimization:** If the `graph` command is used with `--input-db` and DeepCodeGraph determines that no files relevant to the graph have changed since the DB was created (i.e., no LLM scans were performed in the current run), it will skip the graph generation step entirely, saving time and resources. A message will be logged indicating this.
    ```sh
    # Generate a graph using cached data; only new/modified files are fully scanned by LLM
    codegraph graph --path /path/to/your-repo --input-db my_repo_db.json --format plantuml --diagram-type class
    ```

This incremental approach significantly speeds up subsequent analyses of the same repository, especially for large codebases where only a few files might change between scans.

### Examples

To generate a PlantUML class diagram for a local repository, rendered locally as an SVG:
```sh
codegraph graph --path /path/to/repo --format plantuml --diagram-type class --image-format svg --plantuml-service local
```

To generate a Mermaid activity diagram for a GitHub repository, attempting to render an SVG:
```sh
codegraph graph --github https://github.com/username/repository --format mermaid --diagram-type activity --image-format svg
```

To generate a D2 class diagram, saving the `.d2` source (image rendering will be attempted if D2 CLI is installed and an image format is specified):
```sh
codegraph graph --path /path/to/repo --format d2 --diagram-type class --image-format svg 
```

**Using Incremental Scanning:**

Initial export of a repository's structure:
```sh
codegraph export --path /path/to/my-project --output my_project_db.json
```

Later, update the DB with changes from the repository:
```sh
codegraph export --path /path/to/my-project --input-db my_project_db.json --output my_project_db.json
```

Generate a graph using the cached data from `my_project_db.json`. If no files changed, graph generation might be skipped:
```sh
codegraph graph --path /path/to/my-project --input-db my_project_db.json --format plantuml --diagram-type class
```

Run `codegraph -h` for more detailed information on all commands and options.

## Supported Providers

DeepCodeGraph uses [LiteLLM](https://litellm.ai) to provide access to models.

| Provider                      | Supported Models (Examples)                                           | Documentation Link                                                         |
| ----------------------------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **OpenAI**                    | `gpt-4o`, `o3-mini`, etc.                                             | [OpenAI Docs](https://docs.litellm.ai/docs/providers/openai)               |
| **Anthropic**                 | `claude-3.7`, `claude-3.5`, `claude-3`, etc.                          | [Anthropic Docs](https://docs.litellm.ai/docs/providers/anthropic)         |
| **Azure**                     | OpenAI models via Azure                                               | [Azure Docs](https://docs.litellm.ai/docs/providers/azure)                 |
| **Google Vertex AI**          | Various models from Google                                            | [Google Vertex Docs](https://docs.litellm.ai/docs/providers/google_vertex) |
| **Google Gemini (AI Studio)** | `gemini-2.0-pro`, `gemini-2.0-flash`, etc.                            | [Google Gemini Docs](https://docs.litellm.ai/docs/providers/aistudio)      |
| **Mistral AI**                | `mistral-small-latest`, `mistral-medium-latest`, `mixtral-8x7b`, etc. | [Mistral AI Docs](https://docs.litellm.ai/docs/providers/mistral)          |
| **AWS Bedrock**               | Various models from Anthropic, Meta, Deepseek, Mistral, Amazon, etc.  | [AWS Bedrock Docs](https://docs.litellm.ai/docs/providers/bedrock)         |
| **OpenRouter**                | Various models available through OpenRouter                           | [OpenRouter Docs](https://docs.litellm.ai/docs/providers/openrouter)       |
| **Huggingface**               | Various open-source models from Huggingface                           | [Huggingface Docs](https://docs.litellm.ai/docs/providers/huggingface)     |
| **Cohere**                    | `command-r-plus`, `command-r`, `command`, etc.                        | [Cohere Docs](https://docs.litellm.ai/docs/providers/cohere)               |
| **Ollama**                    | Various models like `mistral`, `gemma`, `llama3`, etc.                | [Ollama Docs](https://docs.litellm.ai/docs/providers/ollama)               |
| **Groq**                      | `llama3-8b`, `gemma-7b`, `mixtral-8x7b`, etc.                         | [Groq Docs](https://docs.litellm.ai/docs/providers/groq)                   |

To connect to a provider, set `CODEGRAPH_CUSTOM_API_ENV=1` and the LiteLLM environment variables specified in the docs, or set `CODEGRAPH_API_KEY`.

For example, for [Gemini](https://gemini.google.com/) on [OpenRouter](https://openrouter.ai/):

```sh
# custom setup [api key variable inferred]
export CODEGRAPH_CUSTOM_API_ENV=1
export GEMINI_API_KEY=<your_api_key>

# explicit api key
export CODEGRAPH_API_KEY=<your_api_key>
```

Then set the `CODEGRAPH_LLM_PROVIDER` and `CODEGRAPH_LLM_MODEL` environment variables.

```sh
export CODEGRAPH_LLM_PROVIDER=openrouter
export CODEGRAPH_LLM_MODEL=google/gemini-2.0-flash-lite-preview-02-05:free
```

> Note: The API key variable will be inferred from the provided model and provider unless `CODEGRAPH_API_KEY` is provided.

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
