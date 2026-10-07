/**
 * Serves page.html as a web page.
 * Access is set in appsscript.json ("access": "DOMAIN").
 */
function doGet() {
  return HtmlService.createHtmlOutputFromFile('page')
    .setTitle('Skill Catalog Map')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}
