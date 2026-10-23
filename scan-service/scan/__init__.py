"""scan-service — flatten, clean and assemble photographed exam pages.

SCAN_PIPELINE_VERSION names the bytes this service produces. Any change to
what a page looks like (detection, flatten, illumination, encoding) bumps it;
the backend pins it on every frozen version, and /compile refuses a version
it did not produce (deploy skew fails loudly — 409).
"""
SCAN_PIPELINE_VERSION = "scan-v1.0"
