"""
trafficking/middleware.py

Security headers specifically for trafficking app pages.

Applied only to URLs starting with /report-trafficking/
to avoid interfering with the main HakiMkononi site.

Headers added:
  X-Frame-Options: DENY          — no iframes of report pages
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer   — browser sends no referrer on links away
  Content-Security-Policy        — strict policy for report form
  Cache-Control                  — no caching of sensitive pages
  Permissions-Policy             — disable camera, mic, location

Note: These are defence-in-depth. The main security is:
  1. Partner dashboard requires access key (session auth)
  2. reporter_contact is encrypted at rest
  3. Rate limiting on submissions
  4. No-index meta tags on all pages
  5. Panic button on public pages
"""


class TraffickingSecurityMiddleware:
    """
    Add security headers to all /report-trafficking/ responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only apply to trafficking URLs
        if not request.path.startswith('/report-trafficking/'):
            return response

        # Prevent page from being framed anywhere
        response['X-Frame-Options'] = 'DENY'

        # Prevent MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # No referrer when navigating away — don't leak the URL to KRA etc.
        response['Referrer-Policy'] = 'no-referrer'

        # Strict CSP — only self, Bootstrap CDN, no inline scripts except ours
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "    # needed for inline JS (panic button etc.)
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # No caching of sensitive content
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response['Pragma'] = 'no-cache'

        # Disable unnecessary browser features
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )

        return response
