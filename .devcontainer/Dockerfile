# hadolint global ignore=DL3006
ARG BASE_IMAGE
FROM $BASE_IMAGE

ENV SHELL /bin/bash

ARG USERNAME=mowbot
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Ensure required CLI tools and sudoers directory exist in slim images
RUN apt-get update && apt-get install -y --no-install-recommends sudo docker.io \
  && mkdir -p /etc/sudoers.d \
  && rm -rf /var/lib/apt/lists/*

# Create development user for VS Code
RUN groupadd --gid $USER_GID $USERNAME \
  && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
  && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
  && chmod 0440 /etc/sudoers.d/${USERNAME}

USER $USERNAME