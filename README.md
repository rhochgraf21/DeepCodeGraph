# DeepCodeGraph 

DeepCodeGraph is an LLM agent that automatically generates UML and activity diagrams from codebases using PlantUML.

![Example image of DeepCodeGraph UML diagram.](https://raw.githubusercontent.com/rhochgraf21/DeepCodeGraph/main/examples/simple_oo_python.png)

## Installation

```
git clone https://github.com/rhochgraf21/DeepCodeGraph/
pip install -e codegraph
```

## Usage

The `codegraph` tool is designed to analyze your code repositories by generating dependency graphs or exporting the repository structure. 

Below are the details on how to use the available commands and options.

### Commands

- **graph**  
  Visualize a repository’s dependency graph. Graphs are generated using the public [PlantUML server](https://www.plantuml.com/plantuml).

- **export**  
  Export the repository’s structure for further analysis of the agent progress.

### Global Options

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

- `--path PATH`  
  **Required if not using `--github`.** Provide the local filesystem path to your repository.

- `--github GITHUB_URL`  
  **Required if not using `--path`.** Provide the URL of the GitHub repository to analyze.

### Example

To generate a dependency graph for a local repository located at `/path/to/repo`, run:

```sh
codegraph graph --path /path/to/repo
```

To analyze a GitHub repository, run:

```sh
codegraph graph --github https://github.com/username/repository
```

Run `codegraph -h` for more detailed information.

**Note:** You must provide either the `--path` option (for local repositories) or the `--github` option (for GitHub repositories). The GitHub functionality is provided to analyze repositories hosted on GitHub.

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
