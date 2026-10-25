ARG HA_IMAGE=ghcr.io/home-assistant/home-assistant:stable
FROM ${HA_IMAGE}
COPY custom_components/pax0r_listkeeper/manifest.json /opt/listkeeper-tests/manifest.json
COPY tests/containers/image/ /opt/listkeeper-tests/
RUN python /opt/listkeeper-tests/install_requirements.py
# Run the real HA executable directly; /config belongs only to this test stack.
ENTRYPOINT ["python", "/opt/listkeeper-tests/start.py"]
