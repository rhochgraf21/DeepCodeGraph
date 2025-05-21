# DeepCodeGraph 

DeepCodeGraph is an LLM agent that automatically generates diagrams from codebases, supporting PlantUML, Mermaid, Graphviz, and D2 formats. It can produce both structural (class-like) and behavioral (activity-like) diagrams and offers options for local or web-based rendering for PlantUML.

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

- **PlantUML JAR (for local PlantUML rendering):** Required by the `pythonplantuml` library (listed in `requirements.txt`).
  - Download `plantuml.jar` from the [PlantUML Official Website](https://plantuml.com/download).
  - By default, the application expects it at `/usr/local/bin/plantuml.jar`.
  - Alternatively, set the `PLANTUML_JAR` environment variable to its path:
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
Generates diagrams from a repository. Produces diagram source code and can render images locally if required tools are installed. Supports multiple diagram formats and types (class/activity).

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
  - `local` requires `plantuml.jar` and `pythonplantuml` library. `web` uses the public PlantUML server (PNG only for web).
- `--extensions EXT_LIST`: Comma-separated list of file extensions to scan. Default: `.py,.js,.java,.cpp,.c,.h`.
- `--output DIR`: Directory to save generated graphs. Default: Current directory (`./`).

#### `export` Command
Export the repository’s structure for further analysis of the agent progress.

##### Export Command Options

- `--path PATH`: **Required if not using `--github`.** Local filesystem path to your repository.
- `--github GITHUB_URL`: **Required if not using `--path`.** URL of the GitHub repository to analyze.
- `--extensions EXT_LIST`: Comma-separated list of file extensions to scan. Default: `.py,.js,.java,.cpp,.c,.h`.
- `--format EXPORT_FORMAT`: Export format. Default: `json`. (Note: This `--format` is for the `export` command, distinct from the `graph` command's diagram format).
- `--output FILE_PATH`: Output file path for the exported structure. **Required.**


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
