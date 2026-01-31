# ReaderLM LitServe

[![Open In Studio](https://pl-bolts-doc-images.s3.us-east-2.amazonaws.com/app-2/studio-badge.svg)](https://lightning.ai/sitammeur/studios/readerlm-litserve)

[Jina.ai](https://jina.ai/) has introduced [ReaderLM-v2](https://huggingface.co/jinaai/ReaderLM-v2), a specialized small language model inspired by "Jina Reader" designed for converting raw, noisy HTML from the open web into clean markdown. ReaderLM-v2 features improved markdown generation, supports longer contexts (512K tokens), and outperforms larger LLMs in this specific task, offering a cost-effective and multilingual solution. This project demonstrates the use of the ReaderLM-v2 model for converting HTML content to Markdown content served using LitServe, an easy-to-use, flexible serving engine for AI models built on FastAPI.

## Project Structure

The project is structured as follows:

- `server.py`: The file containing the main code for the web server.
- `client.py`: The file containing the code for client-side requests.
- `requirements.txt`: Python dependencies with pinned versions.
- `.env.template`: Template for environment variable configuration.
- `LICENSE`: The license file for the project.
- `README.md`: The README file that contains information about the project.
- `assets`: The folder containing screenshots for working on the application.
- `.gitignore`: The file containing the list of files and directories to be ignored by Git.

## Tech Stack

- Python (for the programming language)
- PyTorch (for the deep learning framework)
- Hugging Face Transformers Library (for the model)
- LitServe (for the serving engine)

## Getting Started

To get started with this project, follow the steps below:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure environment variables:
   ```bash
   cp .env.template .env
   # Edit .env to customize settings
   ```

3. Run the server:
   ```bash
   python server.py
   ```

4. Upon running the server successfully, you will see uvicorn running on port 8000.

5. Open a new terminal window and run the client:
   ```bash
   python client.py
   ```

Now, you can see the model output based on the HTML content. The model will convert the HTML content to Markdown content.

## Configuration

The server and client can be configured using environment variables. Copy `.env.template` to `.env` and modify as needed.

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `jinaai/ReaderLM-v2` | Hugging Face model name or path |
| `MODEL_REVISION` | `main` | Model revision (commit hash, tag, or branch) |
| `MAX_NEW_TOKENS` | `1024` | Maximum tokens to generate |
| `TEMPERATURE` | `0` | Sampling temperature (0 = deterministic) |
| `REPETITION_PENALTY` | `1.08` | Penalty for repeated tokens |
| `SERVER_PORT` | `8000` | Port to run the server on |

### Client Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_URL` | `http://127.0.0.1:8000` | Base URL of the server |
| `REQUEST_TIMEOUT` | `120` | Request timeout in seconds |

## Usage

The project can be used to serve the ReaderLM-v2 model using LitServe. Here, the model is used to convert HTML content to Markdown content. This suggests potential applications in web scraping, content repurposing, and accessibility improvements.

## Contributing

Contributions are welcome! If you would like to contribute to this project, please raise an issue to discuss the changes you want to make. Once the changes are approved, you can create a pull request.

## License

This project is licensed under the [Apache-2.0 License](LICENSE).

## Contact

If you have any questions or suggestions about the project, please contact me on my GitHub profile.

Happy coding! 🚀
