# ICEGATE login module

Use `~/Documents/icegate-client` for browser-free eSANCHIT and electronic filing. For browser work, find and reuse the existing authenticated dashboard tab at `https://foservices.icegate.gov.in/#/role-dashboard/role-dashboardView` in the user's headed CloakBrowser personal profile. Do not navigate an active dashboard to the login page or reload it merely to check authentication. Keep the dashboard and browser open until the user closes them; do not create another browser using a locked profile. Only open the login route when the dashboard session has actually expired or no authenticated session exists.

The user's ICEGATE credentials are in `~/Documents/icegate-client/.env` (`ICEGATE_USERNAME`, `ICEGATE_PASSWORD`), ignored by git and mode 0600. Read them without printing them, placing them in shell history, or committing the file. Never include credentials or OTPs in chat, screenshots, logs, or committed files. If absent, ask the user to provide credentials securely.

## Browser login

If login is required, open `https://foservices.icegate.gov.in/#/login`, inspect the live page and fill the ICEGATE ID and password. Submit login once, then wait for the OTP. Search Gmail using `gws` for a fresh message from `no-reply@icegate.gov.in` received after this login request; verify the subject identifies the account, extract a unique six-digit OTP only from an explicit OTP phrase, and enter it without displaying it. On 2026-10-28 the email said the OTP is valid for 10 minutes; six single-character fields required real key presses to enable Submit. If unavailable, ambiguous, expired, challenged, or rejected, stop and let the user complete it. Do not repeatedly submit or resend: the existing uploader records a ten-minute login cooldown and a one-hour pause on portal OTP-limit errors. Confirm the authenticated dashboard, not just the form submission.

Better ICEGATE's `src/session/keep-awake.ts` resets the portal's client-side idle timer only while the current session is active; its `src/services/esanchit.ts` invokes the portal's own dashboard SSO handoff. Use the installed userscript when present. The SPA sets a 30-minute client-side idle timeout for external users (`IDLE_TIMEOUT_EXT=1800`) and warns 60 seconds before logout; that timer is driven by user input, not API calls. Client-side keep-awake cannot prevent server-side expiry or sleep.

## Browser-free API authentication (observed 2026-10-28)

A Python `requests` client authenticated against `https://foservices.icegate.gov.in` without a browser, cookies from the browser, or a HAR capture. This is evidence for this account and deployment, not a supported public API. All calls used strict TLS verification.

1. `GET /` first to obtain affinity cookies (`SESSION_AFFINITY`, `TS01...`, and opaque names). All observed cookies were non-persistent.
2. `POST /identity/ext-login` with `{"icegateId": ..., "password": ..., "usertype": "external"}`. The password field is base64 of AES-128-ECB/PKCS7 ciphertext; the key is a constant embedded in the public login JS bundle. A successful response is HTTP 200 with `sessionId`, `token`, `tokenExpiresIn`, `approvedRoles.userRoles[]`, `email`, `mobile`, `userType`, and other profile fields. For this account the only role was `roleId` 3, `Customs Broker`, `userType` `ORGANIZATION`.
3. Authenticated calls send `Authorization: <token>`, `session_id: <sessionId>` and `channel: browser`. `POST /dashboard/services/get` with `{"icegateId": ..., "roleId": 3}` returned 200 and nine services.
4. OTP endpoints (see the warning below): `POST /otp/Ext/otp/{icegateId}` with header `Session_id: <sessionId>` and body `{"email": ..., "mobile": ..., "otpType": "L"}`; `POST /otp/Ext/verify-otp/{icegateId}` with body `{"otp": "NNNNNN", "otpType": "L"}`. The mail comes from `no-reply@icegate.gov.in`, names the account in the subject and states a 10-minute validity.
5. The dashboard token lifetime is exactly 10 minutes (600 seconds) from issue. API activity does not extend it. Once it expires, authenticated calls return HTTP 409 with `auth error..!!!`.
6. `POST /identity/refresh-token` with body `{"icegateId": ..., "sessionId": ...}` and the current `Authorization` header returns `{"token": ..., "tokenExpiresIn": ..., "message": "Success"}`; the new token also lasts 10 minutes. It works only before the old token expires: a refresh attempted about two minutes after expiry returned 409 and did not revive the session. The SPA refreshes every 60 seconds when less than 120 seconds remain, so a kept-open tab slides the token forward. A headless client must refresh on a shorter interval than 10 minutes. A 35-minute keepalive with a refresh every 5 minutes stayed authenticated; one ReadTimeout at +32 minutes was transient and the next probe returned 200, and no 30-minute cap was observed.
7. OTP observations, which must not be presented as a bypass: tokens issued by `ext-login` were accepted by the dashboard and by the eSANCHIT handoff before any OTP call in these tests. Fresh logins at 20:30, 21:05 and 21:12, about 36, 71 and 78 minutes after the last verified OTP at 19:54, still worked without a new OTP. The login bundle supports a client-side-gate explanation: `ext-login` already returns the token, `verify-otp` returns only `{success: true}` and no new token, and on success the SPA stores the same `loginData.token` and sets its own `loggedIn` flag. The OTP screen is an Angular route (`/otp-verification`), not a server-issued upgrade of the token. The code evidence therefore favors a UI-level OTP gate, but an account-level 2FA window is still possible and the tests did not isolate the two. The portal UI and ICEGATE's January 2026 advisory still require OTP. Keep the normal OTP step in any client unless the user explicitly accepts the risk, and never describe OTP as optional in general.
8. Do not call `POST /identity/userLogout/logout` (`{"icegateId", "sessionId", "roleId"}`) during experiments; it ends the server session. Let sessions expire naturally.

## eSANCHIT handoff (observed 2026-10-28)

`POST /esanchit/esanchitDynamicUrl` with `{"icegateId": ..., "roleId": 3, "userType": "organization"}` and the auth headers returns 200 with a single URL. Its query carries `serviceaccount`, `docbase`, `UserType`, `UserCode`, `applicationName`, `userId`, `emailID`, `emailextention`, `digitalSignId`, `displayName` and a `token=DM_TICKET=...` bearer ticket. The ticket must never be logged with its query string.

Follow the handoff like a browser, but never over cleartext:

1. `GET` the returned `https://www.icegate.gov.in/esanchit?...` URL. It returns 302 to `http://www.icegate.gov.in/esanchit/?...`.
2. Rewrite that `Location` to `https://` and `GET` it. It returns 302 to `http://www.icegate.gov.in/esanchit/home` and sets `JSESSIONID`.
3. Rewrite to `https://` and `GET` `/esanchit/home`. It returns 200 with the upload form (`uploadDocs`, `submitDocs`, `fileIn`, `Upload Document`, `Document Type`).

A generic redirect follower will hit port 80; use `allow_redirects=False` and upgrade each hop explicitly. `www.icegate.gov.in` sends HSTS `max-age=31536000; includeSubDomains`, so a browser upgrades automatically, but an HTTP client must do it itself. The host serves an incomplete chain (leaf issued by Entrust DV TLS Issuing RSA CA 2, root Sectigo Public Server Authentication Root R46); strict clients need those intermediates. A local CA bundle containing the system roots plus the intermediates verified without `-k`. Never follow the cleartext URL.

While the dashboard token was valid, a fresh handoff at t0, +4, +8 and +12 minutes all returned a ticket. After the token expired, handoff attempts at +16 and +20 minutes returned 409. Each handoff returns a new ticket and appears to create a new eSANCHIT session; the old `JSESSIONID` was not reusable after expiry. Twelve minutes of silence after a successful handoff left `/esanchit/home` at HTTP 500, consistent with ICEGATE's FAQ statement that the eSANCHIT timeout is "ideally 10 minutes"; the exact cutoff between 0 and 12 minutes was not measured. A new handoff with a valid dashboard token restored access in these tests, including at the end of the 35-minute keepalive.

## Persistence and restart

The SPA stores `token`, `sessionId`, `icegateId`, `loggedIn` and `tokenExpiresIn` in `sessionStorage`, and the cookies are non-persistent. A browser restart therefore cannot resume the dashboard without a new login; one observed restart landed on `#/login`, but the session was already more than an hour old, so that observation did not isolate restart from expiry. A fresh process must run `ext-login` again. Do not save tokens, session IDs or cookies to disk.

## Unknowns

- Whether the server has an absolute session cap beyond 35 minutes. No cap was observed through 35 minutes with refreshes every 5 minutes.
- Whether the pre-OTP acceptance is an account-level 2FA window or absent enforcement on the dashboard/eSANCHIT endpoints.
- Whether a `DM_TICKET` is single-use and how long it remains valid before the first GET.

## Safety rules

- Never log, print or commit passwords, password ciphertext, OTPs, tokens, session IDs, cookies, or full handoff URLs. Log only host, path and query-parameter names.
- Do not upload, stage or submit Documents during authentication research. Those actions need separate user authorization and a reconciliation plan.
- Use the browser-free client for supported operations; if browser work is needed, retain the existing headed personal session.
- Intermittent `ConnectionError` blips occurred during the tests. Retry once, but treat HTTP 409 with `auth error..!!!` as token expiry, not a network fault; do not keep retrying an expired token.
- Evidence journals are outside the repository under `~/.local/state/smart-gmail/`; they contain only non-secret observations. The 2026-10-28 login/OTP, 20-minute monitor, 12-minute expiry/handoff, 35-minute keepalive and fresh-login runs are `browserless-20261028-195340.jsonl`, `monitor-20261028-195533.jsonl`, `recovery-20261028-201752.jsonl`, `keepalive-20261028-203022.jsonl`, `freshlogin-20261028-203014.jsonl` and `freshlogin-20261028-210543.jsonl`.
# Current client (2026-10-29)

Use `~/Documents/icegate-client` for browser-free login and eSANCHIT. The
user requested removal of its OTP fallback; if the dashboard rejects login,
stop and report the error. The browser and OTP details below are historical
research, not instructions to initiate an OTP flow in the client.

