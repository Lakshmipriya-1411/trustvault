class SecurityHeadersMiddleware:
    """Adds browser-side protections and stops authenticated pages being cached."""

    CSP = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Referrer-Policy", "same-origin")
        if request.user.is_authenticated:
            # Back button after logout must not show another person's documents.
            response["Cache-Control"] = "private, no-store"
        return response
