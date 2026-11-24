# uBlock Origin Lite

Bundled upstream: uBlockOrigin/uBOL-home, release `2026.1124.1811`, Chromium package.

Source: https://github.com/uBlockOrigin/uBOL-home/releases/tag/2026.1124.1811

The package's GPL license is retained in `ubol/LICENSE.txt`.
Nova requests broad host permissions for this bundled blocker and initializes
YouTube's Optimal filtering mode through the extension's own messaging API.
Bundled filter code is otherwise maintained upstream.

An enabled extension alone is not a promise of an ad-free YouTube session.
Nova checks registered MAIN-world scriptlets, permissions and enabled rulesets.
The native engine also filters a small set of advertising domains while its
blocker switch is enabled; it does not block Google Video media hosts.
