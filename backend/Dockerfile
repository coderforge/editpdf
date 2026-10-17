# The editpdf service as a container: the same package as the Cloud Builder
# Function, served by Python's HTTP server. Build the package first, from the
# repository root:
#
#   ./scripts/build.sh            (or .\scripts\build.ps1)
#   docker build -t editpdf:1.0.0 backend
#   docker run --rm -p 8787:8787 editpdf:1.0.0
FROM python:3.12-slim

ENV EDITPDF_HOST=0.0.0.0 \
    EDITPDF_PORT=8787 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY dist/function/ ./

USER nobody
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/v1/health', timeout=2)"
CMD ["python", "-m", "editpdf.server"]
