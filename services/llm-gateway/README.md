# LLM Gateway

The LLM gateway is the only layer allowed to call external model APIs.

Agent services pass a constrained task request to this gateway. The gateway applies prompt policy, model routing, payload redaction, provider invocation, and call logging. This keeps provider details and API keys out of business logic.

## Responsibilities

- choose provider and model from task type
- build provider-compatible request payloads
- redact sensitive data before logging
- block prompt-injection patterns in user-controlled inputs
- enforce role-aware generation instructions
- call DeepSeek using the OpenAI-compatible `/chat/completions` endpoint
- return plain answer text to the orchestrator

## Current Provider

- provider: `deepseek`
- base URL: `https://api.deepseek.com`
- model: `deepseek-v4-flash`
- API key env var: `DEEPSEEK_API_KEY`

## Environment

```bash
export DEEPSEEK_API_KEY='...'
export DEEPSEEK_ENABLE_LLM=1
```

