<!-- Generated 2026-09-26 by a research + verification workflow (web research, then a skeptic re-fetched every cited source). Re-verify anything time-sensitive before relying on it. -->

# FACTS SHEET — Stock-portfolio recommendation agent (LangGraph + Claude on Bedrock → AgentCore Runtime)

Date: 2026-09-26. Target region: `ap-southeast-1` (Singapore). Everything stated as fact below was verified against the cited source; "CORRECTION" marks where a common/older claim is wrong. Sourced-but-unverified items are quarantined in §7a.

---

## 1) AgentCore Runtime contract and deploy flow

### 1.1 SDK package
- `bedrock-agentcore` **1.23.1** (2026-09-16), Requires-Python `>=3.10`. Core deps: `boto3>=1.43.72`, `botocore>=1.43.72`, `pydantic>=2.0.0,<2.41.3`, `starlette>=0.46.2`, `uvicorn>=0.34.2`, `websockets>=13.0`, `urllib3>=1.26.0`, `typing-extensions>=4.13.2,<5.0.0`. Extra `bedrock-agentcore[langgraph]` = `langchain>=1.0.0, langgraph>=1.0.0, langchain-mcp-adapters>=0.1.0, httpx>=0.27.0`. (https://pypi.org/pypi/bedrock-agentcore/json ; https://raw.githubusercontent.com/aws/bedrock-agentcore-sdk-python/main/pyproject.toml)

### 1.2 App wrapper (`bedrock_agentcore/runtime/app.py`)
```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp(debug: bool = False, lifespan: Optional[Lifespan] = None, middleware: Sequence[Middleware] | None = None)

@app.entrypoint
def handler(payload, context): ...   # RequestContext is passed ONLY if the 2nd param is literally named `context`
                                     # (_takes_context: len(params) >= 2 and params[1] == "context")

app.run(port: int = 8080, host: Optional[str] = None, **kwargs)
# host = "0.0.0.0" if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER") else "127.0.0.1"
```
- Routes: `POST /invocations`, `GET /ping`, `WebSocket /ws`. Payload = `await request.json()`; invalid JSON → HTTP 400 `{"error": "Invalid JSON", "details": ...}`.
- Return value: plain value → JSON; generator or async generator → `StreamingResponse(..., media_type="text/event-stream")`; a Starlette `Response` is passed through.
- `RequestContext(BaseModel)`: `session_id: Optional[str]`, `request_headers: Optional[Dict[str, str]]`, `request: Optional[Any]`. `BedrockAgentCoreContext.get_workload_access_token() -> Optional[str]`.
- `@app.ping` = custom ping handler; `@app.async_task` flips ping to `HealthyBusy` (raises `ValueError` on non-async functions). `SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"`; `PingStatus.HEALTHY = "Healthy"`, `HEALTHY_BUSY = "HealthyBusy"`.
(https://raw.githubusercontent.com/aws/bedrock-agentcore-sdk-python/main/src/bedrock_agentcore/runtime/app.py ; .../runtime/context.py ; .../runtime/models.py)

### 1.3 HTTP service contract (what the platform expects from your container/zip)
- Host `0.0.0.0`, port `8080`, **ARM64**. `POST /invocations` with `application/json`; respond `application/json` or SSE `text/event-stream` (`data: {...}` lines).
- `GET /ping` → 200 `{"status": "Healthy" | "HealthyBusy"}` (+ optional `time_of_last_update`, Unix seconds — **set only on an actual status change; never bump it every ping** or idle timeout never fires and sessions run to `maxLifetime`). SDK handles ping for you.
- Other protocols: MCP port 8000 `/mcp`; A2A port 9000 `/`; AG-UI port 8080 `/invocations` (SSE) + `/ws`.
- Error mapping (header `x-amzn-ErrorType`): `402 ServiceQuotaExceededException`; `409 ConflictException` / `409 RetryableConflictException` ("Session operation in progress, please retry" — back off and retry); `424 RuntimeClientError` = your container returned 4xx/5xx → CloudWatch; `429 ThrottlingException`. Container startup failures surface as `403 RuntimeClientError` in `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs`.
(https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-troubleshooting.html)

### 1.4 Official AWS LangGraph entrypoint shape (docs verbatim; note the docs still use an old model id)
```python
llm = init_chat_model("us.anthropic.claude-3-5-haiku-20241022-v1:0", model_provider="bedrock_converse")
...
@app.entrypoint
def agent_invocation(payload, context):
    tmp_msg = {"messages": [{"role": "user", "content": str(payload.get("prompt", "No prompt found in input, please guide customer as to what tools can be used"))}]}
    tmp_output = graph.invoke(tmp_msg)
    return {"result": tmp_output['messages'][-1].content}
```
- Security requirement (docs): the payload arrives as parsed JSON, so `prompt` can be any JSON type; a non-string containing a `toolUse` content block can make the framework execute the named tool directly, bypassing model reasoning and guardrails. **Always enforce `isinstance(prompt, str)`** (and reject empty). (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/using-any-agent-framework.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html)

### 1.5 Tooling: Python starter toolkit is DEPRECATED; use the npm AgentCore CLI
- `bedrock-agentcore-starter-toolkit` 0.3.13 (2026-09-15) banner: "The Starter Toolkit CLI is no longer supported. Please use the AgentCore CLI." (https://pypi.org/pypi/bedrock-agentcore-starter-toolkit/json)
- Replacement: npm `@aws/agentcore` **0.30.0** (2026-09-15; dist-tags `latest=0.30.0`, `rc=1.0.0-rc.4`, `preview=1.0.0-preview.31`), `engines.node >=20`, peerDeps `aws-cdk-lib ^2.258.0`, `constructs ^10.0.0`, bin `agentcore`. (https://registry.npmjs.org/@aws/agentcore)
- An old pip `agentcore` binary shadows the npm one: `pip uninstall bedrock-agentcore-starter-toolkit` (CLI README also lists `pipx uninstall` / `uv tool uninstall`). Docs CLI reference is "Auto-generated from @aws/agentcore v0.28.1". (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-reference.html)
- Legacy migration: `agentcore import --source ./path/to/.bedrock_agentcore.yaml -y` copies code into `app/<agent-name>/` and adopts existing runtimes/memories via CloudFormation import; deployment type `direct_code_deploy` maps to build type `CodeZip`. (https://raw.githubusercontent.com/awslabs/agentcore-samples/main/MIGRATION.md)

### 1.6 New CLI workflow (prereqs: Node 20+, Python 3.10+, `uv`, AWS creds; Docker only for `--build Container`)
```bash
npm install -g @aws/agentcore
agentcore create --project-name MyProject --name MyAgent --language Python \
  --framework LangChain_LangGraph --model-provider Bedrock --memory none --build CodeZip --protocol HTTP
#   --language Python|TypeScript (default Python); --framework Strands|LangChain_LangGraph|GoogleADK|OpenAIAgents|VercelAI
#   --model-provider Bedrock|Anthropic|OpenAI|Gemini; --memory none|shortTerm|longAndShortTerm; --build CodeZip|Container (default CodeZip)
#   --protocol HTTP|MCP|A2A|AGUI (default HTTP); --network-mode PUBLIC|VPC; --idle-timeout <60-28800>; --max-lifetime <60-28800>
agentcore dev [prompt] [-p|--port 8080] [-s|--stream] [-b|--no-browser] [-l|--logs] [--skip-deploy] [--no-traces]
agentcore dev "Hello" --stream          # invoke the running dev server
agentcore deploy [--dry-run] [--diff] [-y|--yes] [-v|--verbose] [--target <t>]
agentcore status
agentcore invoke [prompt] [--prompt ...] [--prompt-file ...] [--session-id ...] [--user-id default-user] [--stream] [--json] [--bearer-token ...]
agentcore logs [--since 30m] [--until ...] [--level error|warn|info|debug] [--query "..."] [--json]
agentcore traces list | agentcore traces get <traceId>
agentcore remove all && agentcore deploy   # teardown (there is NO `agentcore destroy` in the new CLI)
```
- `agentcore dev`: creates `.venv`, runs `uv sync` from `pyproject.toml`, starts uvicorn on `0.0.0.0:8080` with hot reload, opens the browser Agent Inspector (`--no-browser` = terminal TUI). Port 8080 must be free.
- `agentcore deploy`: (1) zips code (CodeZip, uploads to S3; no Docker) or builds a container (needs local Docker daemon); (2) CDK synth/provision — first deploy bootstraps CDK and asks confirmation unless `--yes`; (3) creates Runtime + endpoint; (4) configures CloudWatch logging/observability.
- Generated tree: `AGENTS.md`, `README.md`, `agentcore/{agentcore.json, aws-targets.json, cdk/, .env.local}`, `app/<Agent>/{main.py, pyproject.toml, README.md, model/, mcp_client/, skills/}`. **No requirements.txt, no Dockerfile** for CodeZip; project is uv + pyproject.toml only ("Uv is required to create and package the Python project").
- CLI cannot stop sessions ("does not currently support stopping sessions directly") — use `StopRuntimeSession` API.
(https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-reference.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html)

### 1.7 Legacy Python toolkit (0.3.13) — CORRECTIONS to common beliefs
- `agentcore launch` still exists but as a **hidden alias of `deploy`** (`app.command("launch", hidden=True)(deploy)`); docs/samples still show `launch`.
- Default `deployment_type` is **`direct_code_deploy`** (zip), not a CodeBuild container build; CodeBuild is default only when `--deployment-type container`. Dockerfile/.dockerignore generated only for container deployments; `.bedrock_agentcore.yaml` always.
- `agentcore deploy --local`/`-l` = "Run locally for development and testing" (container → Docker/Finch/Podman; direct_code_deploy → runs the script locally with uv). `--local-build`/`-lb` = container-only. `--code-build` is hidden/deprecated ("CodeBuild is now the default").
- `configure` flags: `--entrypoint/-e`, `--name/-n`, `--execution-role/-er`, `--ecr`, `--requirements-file/-rf`, `--protocol/-p`, `--region/-r`, `--deployment-type/-dt (container|direct_code_deploy)`, `--runtime/-rt (PYTHON_3_10..PYTHON_3_13; service default PYTHON_3_11)`, `--s3/-s3`, `--idle-timeout/-it`, `--max-lifetime/-ml`, `--disable-otel`, `--non-interactive/-ni`. Also `invoke [PAYLOAD] -s/-bt/-u/-l`, `status`, `destroy`, `stop-session`.
(https://raw.githubusercontent.com/aws/bedrock-agentcore-starter-toolkit/main/src/bedrock_agentcore_starter_toolkit/cli/cli.py ; .../cli/runtime/commands.py ; .../utils/runtime/config.py ; .../operations/runtime/configure.py)

### 1.8 Direct code deploy (zip) via API — exact shape
- **CORRECTION:** `CodeConfiguration.runtime` valid values are `PYTHON_3_10 | PYTHON_3_11 | PYTHON_3_12 | PYTHON_3_13 | PYTHON_3_14 | NODE_22` (3.14 added Mar 2026; console recommends 3.13). `entryPoint` = array of 1–2 strings, each 1–128 chars. `S3Location` also accepts optional `versionId`.
- arm64 only (aarch64 manylinux wheels); zip ≤ **250 MB zipped / 750 MB unzipped**; files 644, dirs/executables 755; mounted at `/var/task`.
```python
boto3.client('bedrock-agentcore-control').create_agent_runtime(
    agentRuntimeName=...,
    agentRuntimeArtifact={'codeConfiguration': {
        'code': {'s3': {'bucket': 'bedrock-agentcore-code-{account_id}-us-west-2', 'prefix': ...}},
        'runtime': 'PYTHON_3_13',
        'entryPoint': ['opentelemetry-instrument', 'main.py']}},   # drop 'opentelemetry-instrument' if no ADOT dep
    networkConfiguration={'networkMode': 'PUBLIC'},
    roleArn='arn:aws:iam::{account_id}:role/AmazonBedrockAgentCoreSDKRuntime-us-west-2',
    lifecycleConfiguration={'idleRuntimeSessionTimeout': 300, 'maxLifetime': 1800})
# container alternative: agentRuntimeArtifact={'containerConfiguration': {'containerUri': ...}}
```
- AWS-documented manual packaging command:
```bash
uv pip install --python-platform aarch64-manylinux2014 --python-version 3.13 --target=deployment_package --only-binary=:all: -r pyproject.toml
cd deployment_package && zip -r ../deployment_package.zip . && cd .. && zip deployment_package.zip main.py
```
(https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CodeConfiguration.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

### 1.9 Sessions
- Header `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`. Request `runtimeSessionId`: min 33 / max 256 chars (botocore shape `SessionType`, no pattern, `idempotencyToken: true` → boto3 auto-generates if omitted). Response id: 1–100, pattern `[a-zA-Z0-9][a-zA-Z0-9-_]*`. Use `str(uuid.uuid4())`. Each unique id = its own microVM; reuse it for follow-up turns.
- Defaults: `idleRuntimeSessionTimeout` 900 s (resets on each invoke), `maxLifetime` 28800 s (never resets); both range 60–28800 for microVMs (idle up to 1209600 for Instances); idle ≤ max.
- After you update agent code, **existing sessions keep the old version** — use a new session id. Stop: `client.stop_runtime_session(agentRuntimeArn=..., runtimeSessionId=..., qualifier="DEFAULT")`.
(https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_InvokeAgentRuntime.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html ; https://raw.githubusercontent.com/boto/botocore/develop/botocore/data/bedrock-agentcore/2024-02-28/service-2.json)

### 1.10 Invoking a deployed runtime from boto3
```python
import boto3, json, uuid
client = boto3.client('bedrock-agentcore')            # control plane = 'bedrock-agentcore-control'
response = client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,                        # required
    runtimeSessionId=str(uuid.uuid4()),               # >= 33 chars
    payload=json.dumps({"prompt": prompt}).encode(),  # required, max 100,000,000 bytes
    qualifier="DEFAULT")
# other params: contentType, accept, runtimeUserId, traceId, traceParent, traceState, baggage, mcpSessionId, mcpProtocolVersion, mcpMethod, mcpName, accountId
# response keys: runtimeSessionId, contentType, statusCode, response (StreamingBody), trace/mcp headers
if "text/event-stream" in response.get("contentType", ""):
    for line in response["response"].iter_lines(chunk_size=10):
        ...  # if line.startswith("data: "): line = line[6:]
elif response.get("contentType") == "application/json":
    content = [chunk.decode('utf-8') for chunk in response.get("response", [])]
    print(json.loads(''.join(content)))
```
- Caller IAM: `bedrock-agentcore:InvokeAgentRuntime` (+ `bedrock-agentcore:InvokeAgentRuntimeForUser` when sending `X-Amzn-Bedrock-AgentCore-Runtime-User-Id`). Need boto3 ≥ 1.39.8 or you get `Unknown service: 'bedrock-agent-core-runtime'` (docs' "botocore 1.33.8+" figure is inconsistent with lockstep versioning; current boto3 is 1.43.103).
- OAuth/JWT-protected runtimes: boto3 can't send bearer tokens; `POST https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{urllib.parse.quote(arn, safe='')}/invocations?qualifier=DEFAULT` with `Authorization: Bearer`, `Content-Type: application/json`, session header.
(https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-troubleshooting.html)

---

## 2) LangChain/LangGraph agent construction + Bedrock model IDs

### 2.1 Current versions (PyPI, 2026-09-26)
| package | version | date | python |
|---|---|---|---|
| `langchain` | 1.4.2 | 2026-09-18 | >=3.10,<4 |
| `langchain-core` | 1.6.5 | 2026-09-24 | |
| `langgraph` | 1.2.12 | 2026-09-21 | >=3.10 |
| `langchain-aws` | 1.7.9 | 2026-09-22 | >=3.10 |
| `langgraph-checkpoint-aws` | 1.2.3 | 2026-09-03 | >=3.10,<4.0 |
| `boto3` | 1.43.103 | 2026-09-25 | |
- `langchain-aws` 1.7.9 deps: `langchain-core>=1.6.3`, `boto3>=1.43.64`, `pydantic>=2.10.6,<3`, `numpy>=1.0.0,<3`. Install: `pip install -U "langchain[aws]"` (or `langchain-aws`). Recent changelogs show no breaking changes (1.7.8 added readable `model` property on Bedrock chat models). (https://pypi.org/project/langchain-aws/ ; https://raw.githubusercontent.com/langchain-ai/langchain-aws/main/libs/aws/pyproject.toml ; https://docs.langchain.com/oss/python/langchain/models ; https://github.com/langchain-ai/langchain-aws/releases)

### 2.2 Agent factory: use `create_agent`; `create_react_agent` is deprecated
- `langgraph.prebuilt.create_react_agent` is decorated `@deprecated("create_react_agent has been moved to langchain.agents. Please update your import to from langchain.agents import create_agent", category=LangGraphDeprecatedSinceV10)` → since 1.0, expected removal 2.0. Migration is mainly `prompt=` → `system_prompt=`; `create_react_agent` still has `prompt`, `version='v2'`, `pre_model_hook/post_model_hook` which `create_agent` lacks; its `tools` is positional-required. (https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent ; https://docs.langchain.com/oss/python/migrate/langgraph-v1 ; https://raw.githubusercontent.com/langchain-ai/langgraph/main/libs/langgraph/langgraph/warnings.py)
```python
from langchain.agents import create_agent
create_agent(model: str | BaseChatModel, tools: Sequence[BaseTool | Callable[..., Any] | dict[str, Any]] | None = None, *,
    system_prompt: str | SystemMessage | None = None, middleware: Sequence[AgentMiddleware[StateT_co, ContextT]] = (),
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | dict[str, Any] | None = None,
    state_schema: type[AgentState[ResponseT]] | None = None, context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None, store: BaseStore | None = None,
    interrupt_before: list[str] | None = None, interrupt_after: list[str] | None = None, debug: bool = False,
    name: str | None = None, cache: BaseCache[Any] | None = None, transformers: Sequence[TransformerFactory] | None = None
) -> CompiledStateGraph[AgentState[ResponseT], ContextT, InputAgentState, OutputAgentState[ResponseT]]
```
- `model` may be a string id or a chat-model instance; plain callables with docstrings are accepted as tools; `create_agent` calls `bind_tools` for you. (https://reference.langchain.com/python/langchain/agents/factory/create_agent)

### 2.3 Tools
```python
from langchain.tools import tool   # same object as langchain_core.tools.tool
tool(name_or_callable: str | Callable[..., Any] | None = None, runnable: Runnable[Any, Any] | None = None, *args: Any = (),
     description: str | None = None, return_direct: bool = False, args_schema: ArgsSchema | None = None, infer_schema: bool = True,
     response_format: Literal['content', 'content_and_artifact'] = 'content', parse_docstring: bool = False,
     error_on_invalid_docstring: bool = True, extras: dict[str, Any] | None = None)
```
- Docstring → tool description; **type hints are required** (they define the input schema); override with `@tool("custom_name", description=...)` / `args_schema`; a `runtime: ToolRuntime` param is hidden from the model. `langchain.tools.__all__ = ["BaseTool","InjectedState","InjectedStore","InjectedToolArg","InjectedToolCallId","ToolException","ToolRuntime","tool"]`. (https://docs.langchain.com/oss/python/langchain/tools ; https://reference.langchain.com/python/langchain_core/tools/convert/tool)

### 2.4 Bedrock chat model: `ChatBedrockConverse` (recommended)
```python
from langchain_aws import ChatBedrockConverse
llm = ChatBedrockConverse(model_id="global.anthropic.claude-sonnet-4-6", region_name="ap-southeast-1", temperature=..., max_tokens=...)
```
- Fields: `model_id` (alias `model`), `region_name` (falls back to `AWS_REGION`/`AWS_DEFAULT_REGION`/`~/.aws/config`), `temperature` (0–1), `max_tokens`, `top_p`, `provider` (derived from model_id prefix), `credentials_profile_name`, `endpoint_url` (alias `base_url`), `additional_model_request_fields`, `aws_access_key_id/aws_secret_access_key/aws_session_token` (from env), `base_model_id` (alias `base_model`).
- **CORRECTION:** for `us.`/`eu.`/`us-gov.`/`apac.`/`sa.`/`amer.`/`global.`/`jp.`/`au.` prefixes it does NOT call GetInferenceProfile — `_get_base_model()` just strips the prefix (`self.model_id.partition(".")[2]`); `get_inference_profile` is only called when `base_model_id is None and "application-inference-profile" in model_id`.
- Feature table: tool calling ✅, structured output ✅, token streaming ✅, **native async ❌** (async is thread-backed).
```python
bind_tools(self, tools: Sequence[Union[Dict[str, Any], TypeBaseModel, Callable, BaseTool, str, NovaSystemTool]], *,
           tool_choice: Optional[Union[dict, str, Literal["auto", "any"]]] = None, strict: Optional[bool] = None, **kwargs) -> Runnable[LanguageModelInput, AIMessage]
with_structured_output(self, schema: _DictOrPydanticClass, *, include_raw: bool = False,
           method: Literal["function_calling", "json_schema", "prompt_prefill"] = "function_calling", strict: Optional[bool] = None, **kwargs)
```
(https://raw.githubusercontent.com/langchain-ai/langchain-aws/main/libs/aws/langchain_aws/chat_models/bedrock_converse.py ; https://docs.langchain.com/oss/python/integrations/chat/bedrock)
- String-id alternative: `init_chat_model("us.anthropic.claude-sonnet-4-6", model_provider="bedrock_converse")` or `"bedrock_converse:<model>"`; docs don't show passing `region_name` through `init_chat_model` — passing a `ChatBedrockConverse` instance to `create_agent(model=...)` is the documented-safe path. (https://docs.langchain.com/oss/python/langchain/models)
- Three official sources diverge on construction: awslabs sample uses `init_chat_model(..., model_provider="bedrock_converse")`; CLI scaffold uses `ChatBedrock(model_id=...)`; LangChain docs recommend `ChatBedrockConverse`. All work; prefer `ChatBedrockConverse`.

### 2.5 Claude model IDs on Bedrock (AWS model cards) and ap-southeast-1 availability
| model | launch | context / max out | IDs on `bedrock-runtime` |
|---|---|---|---|
| Sonnet 5 | 2026-06-30 | 1M / 128K | bare N/A; `us.`/`eu.`/`au.anthropic.claude-sonnet-5`; `global.anthropic.claude-sonnet-5` |
| Opus 5 | 2026-07-24 | | `anthropic.claude-opus-5`; `us.`/`eu.`/`au.`; `global.anthropic.claude-opus-5` |
| Opus 4.8 | 2026-05-28 | | `anthropic.claude-opus-4-8`; `us.`/`eu.`/`jp.`/`au.`; `global.anthropic.claude-opus-4-8` |
| Sonnet 4.6 | 2026-02-17 | | `anthropic.claude-sonnet-4-6`; `us.`/`eu.`/`au.`/`jp.`; `global.anthropic.claude-sonnet-4-6` |
| Opus 4.6 | 2026-02-05 | | `anthropic.claude-opus-4-6-v1`; `us.`/`eu.`/`au.`; `global.anthropic.claude-opus-4-6-v1` |
| Haiku 4.5 | 2025-10-16 | 200K / 64K | bare N/A; `us.`/`eu.`/`au.`/`jp.anthropic.claude-haiku-4-5-20251001-v1:0`; `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
- Newer models have no dated suffix; **no `apac.` profile exists for 4.6+/5.x**. Full Anthropic list on Bedrock: Opus 5.5, Fable 5.1, Mythos 5.1, Opus 5, Sonnet 5, Mythos 5, Fable 5, Opus 4.8, Opus 4.7, Sonnet 4.6, Opus 4.6, Opus 4.5, Haiku 4.5, Sonnet 4.5, Opus 4.1, Sonnet 4, 3.5 Haiku, 3 Haiku.
- **From `ap-southeast-1` every fetched card shows In-Region ❌ / Geo ❌ / Global ✅ → you MUST use a `global.` profile.** `bedrock-mantle` is not offered in Singapore. Bare model id on-demand fails: `Invocation of model ID anthropic.claude-sonnet-4-5-20250929-v1:0 with on-demand throughput isn't supported. Retry your request with the ID or ARN of an inference profile that contains this model.` (HTTP 400).
- Also confirmed in use: `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (CLI scaffold), `global.anthropic.claude-haiku-4-5-20251001-v1:0` (awslabs sample). Anthropic's page: regional (geo) endpoints carry a 10% premium over global for Sonnet 4.5+; global recommended.
(https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.html ; .../model-card-anthropic-claude-opus-5.html ; .../model-card-anthropic-claude-opus-4-8.html ; .../model-card-anthropic-claude-sonnet-4-6.html ; .../model-card-anthropic-claude-haiku-4-5.html ; .../model-card-anthropic-claude-opus-4-6.html ; https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html ; https://platform.claude.com/docs/en/build-with-claude/claude-on-amazon-bedrock-legacy)

### 2.6 Global cross-region inference (CRIS)
- ~10% cheaper than geo profiles; billed at the **source** region's price; no manual region enablement; CloudTrail logs `additionalEventData.inferenceRegion`.
- IAM (three statements, `bedrock:InvokeModel`): (1) `arn:aws:bedrock:<REQUESTING REGION>:<ACCOUNT>:inference-profile/global.<MODEL NAME>` with `aws:RequestedRegion` = requesting region; (2) `arn:aws:bedrock:<REQUESTING REGION>::foundation-model/<MODEL NAME>` with same + `bedrock:InferenceProfileArn` condition; (3) `arn:aws:bedrock:::foundation-model/<MODEL NAME>` with `"aws:RequestedRegion": "unspecified"` + same InferenceProfileArn condition. SCPs must allow `unspecified` (or use the `bedrock:InferenceProfileArn` exception). (https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html ; https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

### 2.7 Model access
- All Bedrock FMs enabled by default with Marketplace permissions in commercial regions; first invoke auto-subscribes (up to 15 min; missing prereqs → `AccessDeniedException`). IAM: `aws-marketplace:Subscribe/Unsubscribe/ViewSubscriptions` (first time only) + valid payment method. Anthropic requires a one-time use-case form per account/org (individuals may give a GitHub/portfolio URL); not required for `bedrock-mantle`.
```bash
aws bedrock list-foundation-model-agreement-offers --model-id <ModelId>      # AWS CLI >= 2.27.42
aws bedrock put-use-case-for-model-access --form-data <Base64EncodedFormData>
aws bedrock create-foundation-model-agreement --model-id <ModelId> --offer-token <OfferToken>
aws bedrock get-foundation-model-availability --model-id <ModelId>            # expect "agreementAvailability": {"status": "AVAILABLE"}
```
(https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

### 2.8 Invoking / streaming the compiled agent
```python
from langgraph.checkpoint.memory import InMemorySaver
agent = create_agent(model=llm, tools=[...], system_prompt="...", checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": session_id}}
result = agent.invoke({"messages": [{"role": "user", "content": "..."}]}, config=config)
result["messages"]; result["structured_response"]
```
- `stream_mode`: `values | updates | messages | custom | checkpoints (needs checkpointer) | tasks | debug` or a list. `.stream(..., version="v2")` (LangGraph ≥ 1.1) yields `{"type": ..., "ns": (), "data": ...}`; without v2 multiple modes yield `(mode, data)` tuples; `messages` mode yields `(message_chunk, metadata)` with `metadata["langgraph_node"]`. (https://docs.langchain.com/oss/python/langchain/streaming ; https://docs.langchain.com/oss/python/langgraph/streaming)
- **CORRECTION (attribution):** the newer `agent.stream_events(input, version="v3")` / `astream_events` typed-projection API (run object with `.messages` (`.text`, `.reasoning`, `.tool_calls`, `.output`), `.values`, `.output`, `.tool_calls`, `.subagents`, `.subgraphs`, `.extensions`; `str(message.text)` for final text) was "introduced in LangChain v1.3" (not LangGraph 1.2); middleware transformers need `langchain>=1.3.2`; docs contain no experimental warning. (https://docs.langchain.com/oss/python/langchain/event-streaming)

### 2.9 Structured output (portfolio recommendation schema)
```python
from langchain.agents.structured_output import ToolStrategy, ProviderStrategy
ToolStrategy(schema: type[SchemaT] | UnionType | dict[str, Any], *, tool_message_content: str | None = None,
             handle_errors: bool | str | type[Exception] | tuple[type[Exception], ...] | Callable[[Exception], str] = True)
ProviderStrategy(schema: type[SchemaT] | dict[str, Any], *, strict: bool | None = None)
agent = create_agent(model=llm, tools=tools, response_format=ToolStrategy(PortfolioRecommendation))
```
- Bare `response_format=Schema` → AutoStrategy: ProviderStrategy if `model.profile["structured_output"]` or a regex fallback (e.g. `claude-opus-4-(5|6|7|8)`, `claude-sonnet-4-(5|6)`, `claude-haiku-4-5`, `claude-(fable|mythos)-5`) matches, else ToolStrategy. ProviderStrategy on Bedrock becomes Converse `output_config.textFormat.json_schema`. Exceptions: `StructuredOutputError`, `MultipleStructuredOutputsError`, `StructuredOutputValidationError`; `handle_errors=True` retries. **Pass `ToolStrategy(Schema)` explicitly on Bedrock** (safe on every model). (https://docs.langchain.com/oss/python/langchain/structured-output ; https://raw.githubusercontent.com/langchain-ai/langchain/master/libs/langchain_v1/langchain/agents/factory.py)

### 2.10 Optional durable memory (AgentCore Memory)
```python
from langgraph_checkpoint_aws import AgentCoreMemorySaver, AgentCoreMemoryStore
checkpointer = AgentCoreMemorySaver(MEMORY_ID, region_name=REGION)
config = {"configurable": {"thread_id": "session-1", "actor_id": "react-agent-1"}}  # BOTH required (thread_id→session_id, actor_id→actor_id)
```
- Pass `context.session_id` as `thread_id`. Execution role additionally needs `bedrock-agentcore:CreateEvent`, `ListEvents`, `RetrieveMemories`. (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html ; https://pypi.org/pypi/langgraph-checkpoint-aws/json)

---

## 3) Stock data tooling and portfolio math

### 3.1 yfinance
- `yfinance` **1.7.0** (2026-08-26), pure-Python wheel, Apache-2.0, ~25.4k stars, no API key. README: "not affiliated, endorsed, or vetted by Yahoo" / "the Yahoo! finance API is intended for personal use only". No `requires-python` declared; classifiers 3.6–3.13, but `curl_cffi` 0.16.3 needs ≥3.10 → use 3.10+. (https://pypi.org/project/yfinance/ ; https://raw.githubusercontent.com/ranaroussi/yfinance/main/pyproject.toml)
- Deps: `beautifulsoup4>=4.11.1, curl_cffi>=0.15, lxml>=4.9.0, multitasking>=0.0.7, numpy>=1.16.5, pandas>=1.3.0, peewee>=3.16.2, platformdirs>=2.0.0, protobuf>=3.19.0, pytz>=2022.5, requests>=2.31, websockets>=13.0`; extra `yfinance[repair]` = `scipy>=1.6.3, scikit-learn>=1.0`.
- **CORRECTION:** the docs' no-curl_cffi install (`curl .../requirements.txt | grep -vi '^curl_cffi' | pip install -r /dev/stdin`) is broken — `requirements.txt` was deleted 2026-08-01 (HTTP 404). Working: `pip install "beautifulsoup4>=4.11.1" "lxml>=4.9.0" "multitasking>=0.0.7" "numpy>=1.16.5" "pandas>=1.3.0" "peewee>=3.16.2" "platformdirs>=2.0.0" "protobuf>=3.19.0" "pytz>=2022.5" "requests>=2.31" "websockets>=13.0" && pip install --no-deps yfinance`. Without curl_cffi yfinance warns: `curl_cffi not available; falling back to requests without browser TLS impersonation. Yahoo Finance may rate-limit or block this client. Install curl_cffi (>=0.15) for the supported configuration.` Keep curl_cffi.
- Live-verified 2026-09-26 (residential macOS IP, `uv run --python 3.12 --with yfinance`, pandas 3.0.6, curl_cffi 0.16.3): `Ticker('D05.SI').history/.info/.fast_info`, `Ticker('AAPL').info`, `yf.download([...])` all OK (also OK via requests fallback). Plain `curl` to `query2.finance.yahoo.com/v8/finance/chart/D05.SI` → **429** from the same IP. **Cloud/datacenter egress not tested.** (https://github.com/ranaroussi/yfinance)
```python
yf.download(tickers, start=None, end=None, actions=False, threads=True, ignore_tz=None, group_by='column', auto_adjust=True,
            back_adjust=False, repair=False, keepna=False, progress=True, period='1mo if start & end None', interval='1d',
            prepost=False, rounding=False, timeout=10, session=None, multi_level_index=True) -> Optional[pandas.DataFrame]
Ticker(ticker, session=None)
Ticker.history(period=period_default, interval="1d", start=None, end=None, prepost=False, actions=True, auto_adjust=True,
               back_adjust=False, repair=False, keepna=False, rounding=False, timeout=10, raise_errors=False) -> pd.DataFrame
```
- Periods `1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max`; intervals `1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo` (intraday ≤ last 60 days); `start` inclusive, `end` exclusive. `download` multi-ticker → 2-level columns `('Price','Ticker')` e.g. `('Close','AAPL')`, tz-naive `Date` index; single ticker + `multi_level_index=False` → `['Close','High','Low','Open','Volume']`. `history` → `['Open','High','Low','Close','Volume','Dividends','Stock Splits']`, tz-aware index in exchange tz (`Asia/Singapore` for D05.SI). `history` defaults `actions=True`, `download` `actions=False`. (https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html ; https://raw.githubusercontent.com/ranaroussi/yfinance/main/yfinance/scrapers/history.py)
- `Ticker.info` = plain dict (169 keys for D05.SI): `shortName, currency, exchange ('SES'), sector, industry, marketCap, trailingPE, forwardPE, beta, priceToBook, returnOnEquity, fiftyTwoWeekHigh/Low, currentPrice, quoteType`. **GOTCHA:** `info['dividendYield']` is in PERCENT (D05.SI 4.08, AAPL 0.32) while `trailingAnnualDividendYield` is a FRACTION (0.0333); the unit is Yahoo-side (string never appears in yfinance source). Always `.get()`. Guard: `dy = info.get('dividendYield'); dy_frac = (dy/100 if dy is not None and dy > 1 else dy)`. (https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html)
- `Ticker.fast_info` (chart endpoint, no crumb, cheap) exact keys: `currency, dayHigh, dayLow, exchange, fiftyDayAverage, lastPrice, lastVolume, marketCap, open, previousClose, quoteType, regularMarketPreviousClose, shares, tenDayAverageVolume, threeMonthAverageVolume, timezone, twoHundredDayAverage, yearChange, yearHigh, yearLow` (camelCase and snake_case both work). No PE/sector/beta/dividend yield.
- Ticker formats: SGX = `<code>.SI` (D05.SI = DBS, O39.SI = OCBC, SGD, exchange `SES`); US no suffix; mixed `.SI`+US in one `download` call works. Dot share classes must use a dash: `BRK-B`, `BF-B`; `yf.Ticker('BRK.B').fast_info['last_price']` logs "No data found, symbol may be delisted" then raises `KeyError: 'currentTradingPeriod'` → wrap lookups in try/except. (https://sg.finance.yahoo.com/quote/D05.SI/)
- Rate limiting is the main operational risk: `yfinance.exceptions.YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')` (HTTP 429), mostly on `.info` and loops over many tickers; blocks last ~1 h to >24 h; VPN/datacenter IPs affected (EC2 429 on first `.info`, Streamlit Cloud 429). Maintainer: "Stop spamming Yahoo, fetch smarter" (yfinance-cache). Mitigations: one `yf.download` call for all tickers, disk cache, throttle `.info`, `yf.config.network.retries = 2` (default `{"proxy": null, "retries": 0}`; backoff 1s,2s,4s), keep curl_cffi, catch `YFRateLimitError`. Cache dir: `yf.set_tz_cache_location(cache_dir)` (alias of `set_cache_location`; default `platformdirs.user_cache_dir()/py-yfinance`) — set to a writable path such as `/tmp/py-yfinance` in the runtime. Other exceptions: `YFDataException, YFException, YFInvalidPeriodError, YFPricesMissingError, YFTickerMissingError, YFTzMissingError`. (https://github.com/ranaroussi/yfinance/discussions/2431 ; https://ranaroussi.github.io/yfinance/advanced/config.html)

### 3.2 Alternatives (if Yahoo blocks AWS egress)
- **Alpha Vantage**: free = 25 requests/day (official; unlimited for verified open-source/educational); realtime & 15-min-delayed US data premium-only; premium from $49.99/mo (75 req/min) up to $249.99 (1200/min), no daily limits. `alpha_vantage` 3.0.0 is third-party (2024-07-18). 5/min free figure is third-party only. (https://www.alphavantage.co/support/ ; https://www.alphavantage.co/premium/)
- **FMP** (**CORRECTION** to older summaries): Basic $0 = 250 calls/day, EOD, 5 y, US; Starter $29/mo ($19 annual) = 300 calls/min, 5 y, US, annual fundamentals; Premium $69/mo ($49 annual) = 750/min, 30 y, UK+Canada, full fundamentals; **Ultimate $139/mo ($99 annual) = 3,000/min, 30+ y, "Global Coverage"** (SGX inclusion unverified). Bandwidth/30 d: Free 500MB, Starter 20GB, Premium 50GB, Ultimate 150GB. No official SDK (`fmpsdk` 20260824.0, `financialmodelingprep-sdk` 0.3.0 third-party) — use `requests.get('https://financialmodelingprep.com/stable/historical-price-eod/full', params={'symbol':'AAPL','apikey':KEY})`. (https://site.financialmodelingprep.com/pricing-plans)
- **Finnhub**: official `finnhub-python` 2.4.29 (2026-06-24). 429 over plan limit + hard 30 calls/second. `/stock/candle` is `"premium":"Premium Access Required"` (no OHLCV history on free); `/quote`, `/stock/profile2`, `/stock/metric`, `/search`, `/stock/symbol` are free. 60/min free figure is third-party only. (https://finnhub.io/docs/api/rate-limit ; https://finnhub.io/docs/api/stock-candles)
- **Massive (ex-Polygon.io, renamed 2025-10-30)**: official `massive` 2.8.0 (Python ≥3.9,<4; default base `api.massive.com`, `api.polygon.io` still works but old endpoints to be phased out); `polygon-api-client` 1.16.3 legacy. Stocks tiers (non-pros only, US-only): Basic $0 = 5 calls/min, 2 y, EOD; Starter $29/mo unlimited, 5 y, 15-min delayed; Developer $79/mo 10 y; Advanced $199/mo 20+ y realtime. `from massive import RESTClient; RESTClient(api_key=KEY).list_aggs('AAPL', 1, 'day', '2024-01-01', '2026-09-26', limit=50000)`. (https://massive.com/pricing ; https://massive.com/blog/polygon-is-now-massive)

### 3.3 Portfolio math (daily adjusted closes, 252 trading days/yr; live re-run matched)
```python
import numpy as np, pandas as pd, yfinance as yf
px = yf.download(tickers, start="2025-09-26", end="2026-09-26", auto_adjust=True)["Close"]   # columns = tickers
r = px.pct_change().dropna()                     # pandas 3.x: pct_change(fill_method=None) only; NaN handling changes corr
ann_return   = (1 + r).prod() ** (252 / len(r)) - 1
ann_vol      = r.std() * np.sqrt(252)
sharpe       = (r.mean() * 252 - rf) / ann_vol
max_drawdown = (px / px.cummax() - 1).min()
corr         = r.corr()
```
- Sample (1 y to 2026-09-26): AAPL ann_return 0.353, ann_vol 0.243, Sharpe 1.24, MDD −0.138; D05.SI 0.661 / 0.155 / −0.092; MSFT 0.018 / 0.329 / −0.345; O39.SI 1.101 / 0.179 / −0.061; corr(D05.SI,O39.SI) ≈ 0.65, corr(AAPL,D05.SI) ≈ 0.01–0.04 depending on how non-overlapping US/SGX holiday NaN rows are dropped (`dropna(how='any')` vs pairwise). Mixed SGD/USD tickers give local-currency returns; convert with `yf.Ticker('SGDUSD=X').fast_info['last_price']` (0.78296 on 2026-09-26). `DataFrame.pct_change(periods=1, fill_method=None, freq=None, **kwargs)` — `fill_method` must be `None`. (https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.pct_change.html)

### 3.4 Universes
- S&P 500: `pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')` gets HTTP 403 (default UA); fetch with `urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (portfolio-tool)'})` → 503 rows, columns `['Symbol','Security','GICS Sector','GICS Sub-Industry','Headquarters Location','Date added','CIK','Founded']`, dot symbols `BRK.B`, `BF.B` (rewrite to `-`). Same data: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv` (503 rows, same header). (https://en.wikipedia.org/wiki/List_of_S%26P_500_companies)
- STI: exactly 30 constituents, unchanged at the 2026-09-03 FTSE Russell review (effective 2026-09-21; reserve list First Resources, Keppel REIT, Olam Group, Sheng Siong Group, Suntec REIT). Hard-code (append `.SI`): `A17U C38U 9CI C09 D05 D01 J69U BUOU G13 H78 J36 BN4 AJBU ME8U M44U N2IU O39 S58 5E2 U96 C6L S68 Z74 S63 Y92 U11 U14 V03 F34 BS6`.

---

## 4) Official samples and local dev loop

### 4.1 awslabs samples
- Repo is now `awslabs/agentcore-samples` (old `amazon-bedrock-agentcore-samples` URL 301s). Top level: `00-getting-started/`, `01-features/` (01-harness … 08-agents-that-transact), `02-use-cases/`, `03-integrations/`, `04-infrastructure-as-code/`, `05-blueprints/`, `06-workshops/`, `MIGRATION.md`, `pyproject.toml`, `requirements.txt`, `uv.lock`. Root README still links stale `getting-started/python/` paths — repo mid-restructure.
- `03-integrations/agentic-frameworks/langgraph/` = `README.md`, `langgraph_agent_web_search.py`, `requirements.txt`, `observability/{.env.example, README.md, langgraph_travel_agent.py, langgraph_travel_agent_with_session.py, requirements.txt, setup.py}`. `langchain/README.md` just says "Please see 03-langgraph". (https://api.github.com/repos/awslabs/agentcore-samples/contents/03-integrations/agentic-frameworks/langgraph)
- Sample code: `init_chat_model("global.anthropic.claude-haiku-4-5-20251001-v1:0", model_provider="bedrock_converse")`, DuckDuckGoSearchRun, `StateGraph` + `ToolNode` + `tools_condition`, `os.environ["LANGSMITH_OTEL_ENABLED"] = "true"`, sync `agent_invocation(payload, context)` → `{"result": ...}`, `if __name__ == "__main__": app.run()`. **It does NOT validate `isinstance(prompt, str)`** (violates current AWS guidance). Its `requirements.txt` (`langgraph, fastapi, nova-act, langchain-aws, langgraph, langchain_community, pyjwt>=2.10.1, opentelemetry-instrumentation-langchain, bedrock-agentcore, bedrock-agentcore-starter-toolkit, duckduckgo-search`) still pulls the deprecated toolkit and nova-act — drop them. Its README documents only the legacy loop (`uv venv` → `agentcore configure` → `agentcore launch -e langgraph_agent_web_search.py` → `agentcore invoke {"prompt": ...}` → `agentcore destroy`) and mislabels the model as "Claude 3 Haiku". (https://raw.githubusercontent.com/awslabs/agentcore-samples/main/03-integrations/agentic-frameworks/langgraph/langgraph_agent_web_search.py)
- Sample README also shows AgentCore Memory wiring: `AgentCoreMemorySaver(MEMORY_ID, region_name=REGION)` as `checkpointer=`, `AgentCoreMemoryStore(memory_id=MEMORY_ID, region_name=REGION)` as `store=`; tutorials under `01-features/04-manage-context-of-your-agent/memory/{01-short-term-memory,02-long-term-memory}/examples/single-agent/with-langgraph-agent/`. (https://raw.githubusercontent.com/awslabs/agentcore-samples/main/03-integrations/agentic-frameworks/langgraph/README.md)

### 4.2 What `agentcore create --framework LangChain_LangGraph --protocol HTTP` scaffolds (aws/agentcore-cli main)
```python
# app/<Agent>/main.py (Handlebars stripped)
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
LangchainInstrumentor().instrument()
app = BedrockAgentCoreApp()
_CHECKPOINT_LIMIT = 128
_checkpointer = InMemorySaver()          # LRU-evicts threads beyond 128 via _checkpointer.delete_thread

@app.entrypoint
async def invoke(payload, context):
    graph = create_react_agent(get_or_create_model(), tools=mcp_tools + tools, prompt=DEFAULT_SYSTEM_PROMPT, checkpointer=_checkpointer)
    prompt = payload.get("prompt", "What can you help me with?")
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    session_id = getattr(context, "session_id", "default-session")
    touch_thread(session_id)
    result = await graph.ainvoke({"messages": [HumanMessage(content=prompt)]}, config={"configurable": {"thread_id": session_id}})
    return {"result": result["messages"][-1].content}

# model/load.py (Bedrock)
from langchain_aws import ChatBedrock
MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
def load_model() -> ChatBedrock:
    return ChatBedrock(model_id=MODEL_ID)
```
- Scaffold `pyproject.toml`: build `hatchling`; `requires-python = ">=3.10"`; deps `aws-opentelemetry-distro ~= 0.18.0`, `opentelemetry-instrumentation-langchain >= 0.59.0`, `langgraph >= 1.0.2`, `mcp ~= 1.24.0`, `langchain-mcp-adapters >= 0.3.1`, `langchain >= 1.0.3`, `bedrock-agentcore >= 1.8.0`, `botocore[crt] >= 1.35.0`, `langchain-aws >= 1.0.0`. Note it still uses deprecated `create_react_agent` and non-streaming return. Template README says "`agentcore dev` will start a local server on 0.0.0.0:8080." (https://raw.githubusercontent.com/aws/agentcore-cli/main/src/assets/python/http/langchain_langgraph/base/main.py)

### 4.3 Local dev loop
```bash
agentcore dev --no-browser                       # port 8080 must be free; --port to change
curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Hello!"}'
#  -> {"result": "Hello! ..."}
agentcore dev "Recommend a 5-stock SGX/US portfolio" --stream
python main.py                                   # also works: app.run() binds 127.0.0.1:8080 outside Docker
```
- Note `context.session_id` is `None` on a plain local curl (no session header) — fall back to `str(uuid.uuid4())`. The LangChain AWS provider page still documents the legacy `agentcore configure` / `agentcore launch -e your_agent.py` (open langchain-ai/docs issue #6091, 2026-09-18). (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-code-deploy-python.html ; https://github.com/langchain-ai/docs/issues/6091)

### 4.4 Post-deploy smoke test
```bash
agentcore deploy --dry-run && agentcore deploy --yes
agentcore status
agentcore invoke --prompt "Hello, what can you do?"
agentcore logs --since 30m --level error
```
Or boto3 `invoke_agent_runtime` per §1.10.

### 4.5 Observability
- Log group `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>`, stream `runtime-logs`; new agents write spans to a `spans` stream in the same group (needs ADOT `aws-opentelemetry-distro>=0.18.0`, `logs:PutResourcePolicy` on the execution role, env `UNIFIED_TRACES_DESTINATION_ENABLED=true`). Traces require CloudWatch Transaction Search once per account: `aws logs put-resource-policy --policy-name MyResourcePolicy ...` (Principal `xray.amazonaws.com`, `logs:PutLogEvents` on `log-group:aws/spans:*` and `/aws/application-signals/data:*`) then `aws xray update-trace-segment-destination --destination CloudWatchLogs`. Auto-instrument: `opentelemetry-instrument python main.py` (CodeZip `entryPoint: ['opentelemetry-instrument','main.py']`, Dockerfile `CMD ["opentelemetry-instrument", "python", "main.py"]`). Disable: `DISABLE_ADOT_OBSERVABILITY=true`. Dashboard: CloudWatch GenAI Observability. Docs misspell the package as `opentelemetry-instrument-langchain`; correct name is `opentelemetry-instrumentation-langchain` (`LangchainInstrumentor().instrument()`). (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)

---

## 5) IAM / cost / region notes

### 5.1 Execution role (assumed by the runtime)
- Trust: `Principal {"Service": "bedrock-agentcore.amazonaws.com"}`, `sts:AssumeRole`, `Condition: StringEquals aws:SourceAccount "<acct>", ArnLike aws:SourceArn "arn:aws:bedrock-agentcore:<region>:<acct>:*"`.
- Container role statements: `ecr:BatchGetImage, ecr:GetDownloadUrlForLayer` on `repository/*`; `ecr:GetAuthorizationToken` on `*`; `logs:DescribeLogStreams, logs:CreateLogGroup` on `log-group:/aws/bedrock-agentcore/runtimes/*`; `logs:PutResourcePolicy` on `.../runtimes/<agentName>-*`; `logs:DescribeLogGroups` on `log-group:*`; `logs:CreateLogStream, logs:PutLogEvents` on `.../runtimes/*:log-stream:*`; `xray:PutTraceSegments, PutTelemetryRecords, GetSamplingRules, GetSamplingTargets`; `cloudwatch:PutMetricData` with `cloudwatch:namespace = bedrock-agentcore`; `bedrock-agentcore:GetWorkloadAccessToken[ForJWT|ForUserId]` on `workload-identity-directory/default` and `.../workload-identity/<agentName>-*`; `bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream` on `arn:aws:bedrock:*::foundation-model/*` and `arn:aws:bedrock:<region>:<acct>:*`.
- The documented **direct-deploy (zip) role** drops BOTH ECR statements AND the GetWorkloadAccessToken statement; its JSON has **no S3 statement**, although the code-deploy page's prose says the role needs "S3 access permissions for your deployment package". Since 2025-10-13 workload-identity permissions for new agents come from the service-linked role `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`.
- Memory adds `bedrock-agentcore:CreateEvent, ListEvents, RetrieveMemories`.
(https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html)

### 5.2 Deploying identity
- `BedrockAgentCoreFullAccess` managed policy + the docs "Use the AgentCore CLI" policy (Sids `IAMRoleManagement` on `role/*BedrockAgentCore*`, `IAMPassRoleAccess` on `role/AmazonBedrockAgentCore*`, `CodeBuildProjectAccess` on `project/bedrock-agentcore-*`, `CloudWatchLogsAccess`, `S3Access` on `arn:aws:s3:::bedrock-agentcore-*`, `ECRRepositoryAccess` on `repository/bedrock-agentcore-*`, `ECRAuthorizationAccess`). New CLI additionally needs `sts:AssumeRole` on the four CDK bootstrap roles (`cdk-*-deploy`, `file-publishing`, `image-publishing`, `lookup`), `cloudformation:*`, `sts:GetCallerIdentity`, `tag:GetResources`, `iam:CreateRole/DeleteRole/PutRolePolicy/PassRole` on `role/AgentCore-*`, `logs:StartLiveTail/FilterLogEvents/StartQuery/GetQueryResults/DescribeResourcePolicies/PutResourcePolicy`, `xray:GetTraceSegmentDestination/UpdateTraceSegmentDestination/UpdateIndexingRule` (ready-made `docs/policies/iam-policy-user.json`, `iam-policy-cfn-execution.json`, `iam-policy-boundary.json`). AWS: these CLI policies are for dev/test, not production. (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html ; https://github.com/aws/agentcore-cli/blob/main/docs/PERMISSIONS.md)

### 5.3 Regions
- AgentCore is in 22 regions incl. **Asia Pacific (Singapore)**: Runtime microVMs ✅, Runtime Instances ✅, harness ✅, Memory ✅, Gateway ✅, Identity ✅, Built-in Tools ✅, Observability ✅, payments ✅, Policy ✅, Evaluations ✅, optimization ✅; Agent Registry ❌, Web Search Tool ❌. (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)
- Bedrock Claude from Singapore: global profiles only (§2.5); price is based on the source region, global ≈10% cheaper than geo (§2.6). Anthropic use-case form once per account/org; opt-in regions require it again (§2.7).

### 5.4 AgentCore Runtime pricing (no AgentCore-specific free tier; only generic "up to $200" new-customer credits)
- v1 microVMs: CPU $0.0895/vCPU-h, memory $0.00945/GB-h. v2: consumption CPU $0.1276/vCPU-h, memory $0.0169/GB-h; committed baseline $0.0997 / $0.0132 "launching by October 2026". Per-second billing, 1-s minimum; CPU scales to zero during I/O wait (LLM/tool calls); memory billed at peak, v2 reclaims idle memory after 120 s. Example: 1M sessions/month × 10 min × 90% I/O wait = $0.002127 CPU + $0.004576 memory = $0.006703/session ≈ $6,703/month. (https://aws.amazon.com/bedrock/agentcore/pricing/)

---

## 6) Recommended minimal stack (pin these)

Use Python **3.13** (CodeZip runtime `PYTHON_3_13`) in a `uv venv`, scaffolded by `@aws/agentcore@0.30.0` (`agentcore create … --framework LangChain_LangGraph --model-provider Bedrock --build CodeZip --protocol HTTP --memory none`), region `ap-southeast-1`; pin in `pyproject.toml`: `bedrock-agentcore==1.23.1`, `langchain==1.4.2`, `langchain-core==1.6.5`, `langgraph==1.2.12`, `langchain-aws==1.7.9`, `boto3==1.43.103`, `yfinance==1.7.0`, `curl_cffi==0.16.3`, `pandas==3.0.6`, `numpy==2.5.3`, `aws-opentelemetry-distro~=0.18.0`, `opentelemetry-instrumentation-langchain>=0.59.0` (drop the scaffold's `mcp`/`langchain-mcp-adapters` unless you use MCP); replace the scaffold's `create_react_agent`/`ChatBedrock` with `create_agent(model=ChatBedrockConverse(model_id="global.anthropic.claude-sonnet-4-6", region_name="ap-southeast-1", temperature=0.2, max_tokens=4096), tools=[...yfinance @tool functions...], system_prompt=..., response_format=ToolStrategy(PortfolioRecommendation), checkpointer=InMemorySaver())` (dev/cheap tier: `global.anthropic.claude-haiku-4-5-20251001-v1:0`); entrypoint `async def invoke(payload, context)` that enforces `isinstance(prompt, str)`, uses `context.session_id or str(uuid.uuid4())` as `thread_id`, returns `{"result": ..., "portfolio": result["structured_response"].model_dump()}`; tools call `yf.download` once per request (never loop `.info` over a universe), set `yf.config.network.retries = 2`, `yf.set_tz_cache_location("/tmp/py-yfinance")`, catch `YFRateLimitError`, and return only the computed metrics table (ann. return, vol, Sharpe, MDD, correlation, `dividendYield` unit-guarded) to the model; execution role = documented direct-deploy role + the three-statement global-CRIS `bedrock:InvokeModel` policy (§2.6) + `bedrock:InvokeModelWithResponseStream`; deploy with `agentcore deploy --yes`, verify with `agentcore invoke --prompt ...` and `agentcore logs --since 30m --level error`.

---

## 7) Open questions

### 7a. Unverified, check before relying on (sourced but not independently verified)
- **AgentCore Runtime V2** (announced 2026-09-18): opt in via `platformVersion: "V2"` on Create/UpdateAgentRuntime (botocore has the field, string 1–128); claimed P75 cold start 1.9–2.0 s; launch regions us-east-1, us-east-2, us-west-2, eu-west-1, ap-northeast-1 only — **not ap-southeast-1**. (https://aws.amazon.com/about-aws/whats-new/2026/09/new-agentcore-runtime-generally-available/)
- CLI 1.0 imminent: `1.0.0-rc.4` (2026-09-22) on npm; docs reference is v0.28.1; 0.28.1→0.30.0 changes reportedly limited to evaluator flags / project schema v2. Flags may change in 1.0. (https://registry.npmjs.org/@aws/agentcore ; https://github.com/aws/agentcore-cli/releases)
- New-CLI execution role is auto-created by the CDK `aws-bedrockagentcore.Runtime` construct via `@aws/agentcore-cdk` `AgentCoreApplication` (grants ECR pull, Logs, X-Ray, `bedrock:InvokeModel`, `GetWorkloadAccessToken`); role name is CDK-generated/undocumented; extend with `env.runtime.role.addToPrincipalPolicy(...)` in `agentcore/cdk/lib/cdk-stack.ts`. (https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_bedrockagentcore-readme.html)
- CodeZip packager (`src/lib/packaging/python.ts`, 0.30.0) runs `uv pip install -r <pyproject.toml> --target <staging> --python-version <x> --python-platform <p> --only-binary :all:` trying `['aarch64-manylinux2014','aarch64-manylinux_2_28','aarch64-manylinux_2_34']` in order (AL2023, glibc 2.34); `MAX_ZIP_SIZE_BYTES = 250*1024*1024`. Current `numpy-2.5.3` / `pandas-3.0.6` cp313 aarch64 wheels are tagged `manylinux_2_28` (lxml/curl_cffi are manylinux2014), so the AWS-documented manual `--python-platform aarch64-manylinux2014` command may fail to resolve — use `aarch64-manylinux_2_28` or let `agentcore deploy` package. (https://github.com/aws/agentcore-cli/blob/main/src/lib/packaging/python.ts ; https://pypi.org/pypi/numpy/json ; https://pypi.org/pypi/pandas/json)
- `agentcore invoke --dev` printed by generated template READMEs is NOT a real flag in 0.30.0; use `agentcore dev "<prompt>" [--stream]`. (https://github.com/aws/agentcore-cli/blob/main/src/cli/commands/invoke/command.tsx)
- Bedrock API keys: `ChatBedrockConverse(..., api_key="...")` or env `AWS_BEARER_TOKEN_BEDROCK` (field `bedrock_api_key`, alias `api_key`); sets a process-wide env var, not multi-tenant safe. (https://raw.githubusercontent.com/langchain-ai/langchain-aws/main/libs/aws/langchain_aws/chat_models/bedrock_converse.py)
- Bare `response_format=Schema` auto-selection per `langchain-aws/data/_profiles.py`: `global.anthropic.claude-sonnet-5` → `structured_output: False` → ToolStrategy; `global.anthropic.claude-opus-5` → key absent, no regex → ToolStrategy; `global.anthropic.claude-opus-4-8` → regex match → ProviderStrategy (Converse `output_config.textFormat json_schema`) although the AWS card lists structured outputs as unsupported — likely API failure; `global.anthropic.claude-sonnet-4-6`, `global.anthropic.claude-opus-4-6-v1`, `global.anthropic.claude-haiku-4-5-20251001-v1:0` → `structured_output: True` → ProviderStrategy (AWS says supported). Rule: pass `ToolStrategy` explicitly. (https://raw.githubusercontent.com/langchain-ai/langchain-aws/main/libs/aws/langchain_aws/data/_profiles.py)
- Sonnet 5 / Opus 5 on Bedrock: adaptive thinking ON by default even when `thinking` omitted; disable via `additional_model_request_fields={"thinking": {"type": "disabled"}}` (Opus 5: effort capped at high when disabled). Sonnet 5 knowledge cutoff Jan 2026, Opus 5 May 2026. Prompt-cache minimums: 1,024 tokens (Sonnet 5), 512 (Opus 5), 4,096 (Haiku 4.5). (https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.html)
- `yfinance-cache` 0.9.3 (2026-08-26, Python ≥3.9): `import yfinance_cache as yfc; yfc.Ticker('D05.SI').history(period='1y')`, persistent cache re-fetching only stale rows. (https://pypi.org/project/yfinance-cache/)
- Memory tutorial detail: `AgentCoreMemorySaver` raises `InvalidConfigError` unless both `thread_id` and `actor_id` are in `configurable`; `AgentCoreMemoryStore` needs a memory strategy. (https://raw.githubusercontent.com/awslabs/agentcore-samples/main/03-integrations/agentic-frameworks/langgraph/README.md)
- Region history: Singapore listed in the regions table; Thailand/Malaysia/Milan/Spain added Jun 2026, N. California/Hyderabad Aug 2026; Runtime "Instances" (EC2 in your account, ≤14-day sessions) GA Aug 2026. (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html)

### 7b. Open questions (nobody has verified these)
1. **Does Yahoo Finance block AgentCore Runtime egress IPs?** Evidence datacenter IPs get 429 (EC2 discussion #2581, Streamlit Cloud). Smoke-test `yf.download(['D05.SI','AAPL'], period='5d')` from a deployed runtime before committing to yfinance; have FMP/Massive/Finnhub fallback ready. Also: Yahoo's "personal use only" terms vs. an app that recommends investments to others — legal suitability unassessed.
2. `runtimeSessionId` request-side allowed characters (no server pattern documented; uuid4 is safe; `.`/`:` untested).
3. Whether the service reads the CodeZip S3 object with its own credentials or the execution role (no S3 grant found in CLI CDK code or the documented direct-deploy role JSON, but prose says S3 access is needed).
4. Which Python minor `agentcore deploy` selects for the CodeZip runtime (CLI docs say "Python 3.12+", AWS docs "3.10 or later", template `>=3.10`, API allows up to 3.14); whether the legacy toolkit accepts `PYTHON_3_14`.
5. Whether `agentcore create --framework LangChain_LangGraph` will switch to the newer `create_agent`-based streaming template from PR #2230 (merged 2026-09-04) — `main` still ships `create_react_agent`.
6. Bedrock behavior when `output_config.textFormat json_schema` is sent to Opus 4.8 / Sonnet 5 / Opus 5 (ValidationException vs. ignored). Use ToolStrategy / `method="function_calling"` until tested.
7. Whether Converse accepts `temperature=0.2` alongside default-on adaptive thinking for Sonnet 5 / Opus 5, or requires `thinking: disabled`.
8. Streaming IAM: CRIS docs only grant `bedrock:InvokeModel`; whether ConverseStream needs `bedrock:InvokeModelWithResponseStream` under global profiles was not verified (grant both to be safe). Whether the default execution role's `arn:aws:bedrock:*::foundation-model/*` matches the region-less FM ARN needed by global CRIS from ap-southeast-1.
9. Per-source-region pricing of `global.*` profiles invoked from ap-southeast-1 (pricing page not fetched); availability of `global.anthropic.claude-sonnet-4-5-20250929-v1:0` from Singapore (card not fetched; Haiku 4.5 / Sonnet 4.6 / 5 / Opus 4.6 / 4.8 / 5 confirmed Global ✅).
10. `init_chat_model(..., model_provider="bedrock_converse", region_name=...)` kwarg forwarding — assumed, not shown in docs.
11. `stream_events(version="v3")` token/usage_metadata accounting; throughput of thread-backed async `ChatBedrockConverse` under concurrency.
12. Cross-source ID discrepancies unresolved via live API (`aws bedrock list-inference-profiles` not run): AWS lists `jp.anthropic.claude-haiku-4-5-20251001-v1:0` while Anthropic says jp: No; Anthropic says apac: Yes for Opus 4.6 while AWS lists only us./eu./au. Irrelevant for Singapore (global only).
13. Whether the Anthropic first-time-use form is already satisfied for this account/org: `aws bedrock get-foundation-model-availability --model-id anthropic.claude-sonnet-4-6` (expect `agreementAvailability.status == "AVAILABLE"`).
14. `dividendYield` percent-unit change date on Yahoo's side is unknown; pin `yfinance>=1.7.0,<2` and unit-test the guard. FMP "Global Coverage" inclusion of SGX unverified. `financialmodelingprep-sdk` async-only claim unverified.
15. pandas 3.0.6 + yfinance 1.7.0 passed every call exercised, but yfinance only declares `pandas>=1.3.0`; no exhaustive compatibility test.
16. Running the awslabs LangGraph sample under the new CLI (create + replace `main.py`, or `agentcore import --source`) was not executed; what `agentcore import` synthesizes into `pyproject.toml` from a `requirements.txt` project was not read.