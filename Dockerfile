FROM python:3.12-slim

RUN pip install --no-cache-dir piiwall

EXPOSE 8111

# Override with --preset, --port etc. at runtime.
# Example:
#   docker run -p 8111:8111 piiwall proxy --preset dpdp,pci
#
# Then in your app:
#   ANTHROPIC_BASE_URL=http://localhost:8111
#   OPENAI_BASE_URL=http://localhost:8111/openai/v1
ENTRYPOINT ["piiwall", "proxy", "--port", "8111"]
CMD ["--preset", "dpdp"]
