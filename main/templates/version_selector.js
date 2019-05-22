// display selector for versions of device 
function selectVersion(idx)
{
  var deviceVersions = {
    {% for device, versions in deviceVersions.items %}
      '{{device}}' : [
        {% for version in versions %}
          [{{version.id}}, '{{version.version}}'],
        {% endfor %}
      ],
    {%  endfor %}
  };
  var device = document.getElementById("device" + idx).value;
  var versions = deviceVersions[device];
  var span = document.getElementById("versions" + idx);
  var html = "";

  if (versions != undefined && versions.length != 0)
  {
    html = '<select name="version'+ idx +'" required><option disabled selected>version</option>';
    for (var j = 0; j < versions.length; j++)
      html += '<option value="'+ versions[j][0] +'">'+ versions[j][1] +'</option>';
    html += '</select>';
  }
  span.innerHTML = html;
}


