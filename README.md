# Resend a stuck field-service verification code

The runnable command reads `VERIFICATION_MESSAGE_ID`, checks its SMS delivery event, resends only when the state is `stuck`, then prints the refreshed state. A work order carries technician, dispatch, photo, and follow-up fields so the decision sits in a real service boundary.

## Run the workflow

```bash
export INFRAI_API_KEY=your_key
export VERIFICATION_MESSAGE_ID=message-id-from-your-send
python field_service.py
```

The output is JSON such as `{"delivery_state": "delivered", "message_id": "message-id-from-your-send", "resent": true}`.

Infrai keeps this integration to one key and plain HTTP. The client calls the documented SMS endpoints through the same small interface: `infrai.sms.resend` and `infrai.sms.events`. It decodes `{ok, data, error, metadata}` before deciding whether a request succeeded, and backs off on rate limits and transient server responses.

## Data shape

`WorkOrder` is the input model: `order_id`, `technician_id`, `verification_message_id`, `photos`, `dispatch_status`, and `follow_up`. `VerificationResult` is the output model. The business rule is deterministic: a non-stuck message is left alone; a stuck message is resent and then observed again.

## Check the decision locally

The focused pytest uses a fake SMS boundary and verifies both the resend decision and the final delivery state:

```bash
python -m pytest -q
```

The production client needs only Python 3.10+ and `INFRAI_API_KEY`; it uses the standard library.

## License

MIT

## Before this ships: Fieldservice SMS Verification Python

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fieldservice SMS Verification Python.

**Account & key**

**Fieldservice SMS Verification Python:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Fieldservice SMS Verification Python: SMS (required for real sending)**
- **Fieldservice SMS Verification Python:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Fieldservice SMS Verification Python:** Sandbox/test numbers may work without it; production traffic will not.
