const urlAdaptor = new UV.IIIFURLAdaptor();
const manifestFromUrl = urlAdaptor.get("manifest");

if (manifestFromUrl !== undefined)
{
    const data = urlAdaptor.getInitialData({
        manifest: manifestFromUrl,
    });

    uv = UV.init("uv", data);
    urlAdaptor.bindTo(uv);
}
