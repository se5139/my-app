# Policy Sources

Last reviewed: 2026-06-09

This app should use official sources first when checking policy-sensitive behavior.

## YouTube Sources

- YouTube Shorts monetization policies: https://support.google.com/youtube/answer/12504220
- YouTube channel monetization policies: https://support.google.com/youtube/answer/1311392
- Disclosing altered or synthetic content: https://support.google.com/youtube/answer/14328491
- Fair use on YouTube: https://support.google.com/youtube/answer/9783148
- YouTube API Services developer policies: https://developers.google.com/youtube/terms/developer-policies
- YouTube Data API quota and compliance audits: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- YouTube videos.insert reference: https://developers.google.com/youtube/v3/docs/videos/insert

## Product Rules Derived From These Sources

- Treat non-original or minimally edited reused videos as high risk.
- Treat claimed third-party music/video/TV/movie clips as high risk unless the user provides rights documentation and a transformation note.
- Require synthetic/altered disclosure when realistic AI or edited media could make viewers think something real happened.
- Keep uploads private or disabled until review gates pass.
- Do not automate fake views, engagement, or policy circumvention.
- Keep API credentials local and never commit them.
- Track quota cost for API calls before enabling automated collection or upload.

## Legal Note

This app can provide workflow checks and risk flags, but it is not legal advice. If a draft depends on fair use, rights clearance, likeness rights, trademark use, financial/medical claims, or controversial public figures, the app should flag the draft for human or professional review.
