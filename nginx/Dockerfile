FROM nginx:1.24
ARG LEGOCHECKSUM="f5a978397802a2eb20771925ceb173dff88705b45fdbb2e68312269e205fa85d"
RUN curl -LJO https://github.com/go-acme/lego/releases/download/v4.14.2/lego_v4.14.2_linux_amd64.tar.gz && \
    echo "$LEGOCHECKSUM lego_v4.14.2_linux_amd64.tar.gz" | sha256sum -c && \
    tar -xvf lego_v4.14.2_linux_amd64.tar.gz && \
    mv lego /usr/local/bin/lego && \
    rm lego_v4.14.2_linux_amd64.tar.gz
COPY error_pages .