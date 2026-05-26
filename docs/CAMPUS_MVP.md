# Campus Operations MVP

This repo now includes a campus operations MVP built on top of the gaokao-agent runtime skeleton.

## Scope

- WeCom OAuth H5 redirect, HttpOnly session issuance, and DB-backed user mapping
- WeCom AI Bot long-connection bridge for public consultation messages
- Parent/student H5 leave submission
- Meal order / cancellation / locked summary / vendor confirmation
- Repair ticket creation / assignment / completion / closure
- Daily report generation
- Admin console list views for leave, meal, repair, and report

## API Surface

- `POST /api/campus/auth/wecom/state`
- `GET /api/campus/auth/wecom/start?redirect_path=/h5/...`
- `GET /api/campus/auth/wecom/callback`
- `POST /api/campus/leaves`
- `GET /api/campus/leaves`
- `GET /api/campus/leaves/:id`
- `POST /api/campus/leaves/:id/approve`
- `POST /api/campus/leaves/:id/reject`
- `POST /api/campus/meals/orders`
- `POST /api/campus/meals/orders/:id/cancel`
- `GET /api/campus/meals/summary?date=YYYY-MM-DD`
- `POST /api/campus/meals/delivery/:id/confirm`
- `POST /api/campus/repairs`
- `GET /api/campus/repairs`
- `GET /api/campus/repairs/:id`
- `POST /api/campus/repairs/:id/assign`
- `POST /api/campus/repairs/:id/complete`
- `POST /api/campus/repairs/:id/close`
- `GET /api/campus/reports/daily?date=YYYY-MM-DD`

## Roles

- `parent_or_student_h5`
- `vendor_link_user`
- `head_teacher`
- `academic_staff`
- `logistics_staff`
- `repair_assignee`
- `school_admin`
- `super_admin`

## Tests

- `make test-campus-auth`
- `make test-wecom-adapter`
- `make test-wecom-aibot`
- `make test-campus-flow`
- `make test-campus-rls-live`

## WeCom Integration Modes

`services/wecom-adapter` is for the school's self-built application REST APIs, such as OAuth, app messages, and parent notifications. It requires `WECOM_CORP_ID` and `WECOM_APP_SECRET`. In production, opening `/h5/*` starts OAuth automatically; the callback maps imported `campus_users.wecom_userid` or `students.parent_userid`, issues an eight-hour HttpOnly session cookie, and redirects to the requested H5 page. Deploy H5 and API on the same HTTPS `APP_BASE_URL`.

`services/wecom-aibot-bridge` is for an API-mode smart bot created with a `Bot ID` and `Secret`. It connects through the official WebSocket SDK and forwards text messages to `/api/gaokao/chat` as a `customer` identity only.

Configure the AI bot locally in `.env`:

```bash
WECOM_AIBOT_BOT_ID=<bot-id>
WECOM_AIBOT_SECRET=<bot-secret>
WECOM_AIBOT_API_URL=http://127.0.0.1:8787/api/gaokao/chat
WECOM_AIBOT_TRUSTED_PROXY_TOKEN=<trusted-proxy-token>
```

Start the API first, then the bridge:

```bash
make demo-api
make run-wecom-aibot
```
