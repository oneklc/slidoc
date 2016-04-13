// JS include file for Google services
// Before including this script, define CLIENT_ID, API_KEY, LOGIN_BUTTON_ID, AUTH_CALLBACK and
//   function onGoogleAPILoad() { GService.onGoogleAPILoad(); }
// After this script, include script with src="https://apis.google.com/js/client.js?onload=onGoogleAPILoad"

var GService = {};

(function (GService) {
// http://railsrescue.com/blog/2015-05-28-step-by-step-setup-to-send-form-data-to-google-sheets/

GService.sendData = function (data, url, callback) {
  /// callback(result_obj, optional_err_msg)

  var XHR = new XMLHttpRequest();
  var urlEncodedData = "";
  var urlEncodedDataPairs = [];

  XHR.onreadystatechange = function () {
      var DONE = 4; // readyState 4 means the request is done.
      var OK = 200; // status 200 is a successful return.
      if (XHR.readyState === DONE) {
        if (XHR.status === OK) {
          console.log('XHR: '+XHR.status, XHR.responseText);
          if (callback) {
             var obj = null;
             var msg = '';
             try {
                 obj = JSON.parse(XHR.responseText)
             } catch (err) {
                 console.log('JSON parsing error:', err, XHR.responseText);
                 msg = 'JSON parsing error';
             }
             callback(obj, msg);
          }
        } else {
          console.log('XHR Error: '+XHR.status, XHR.responseText);
          callback(null, 'Error in HTTP request')
        }
      }
  };

  // We turn the data object into an array of URL encoded key value pairs.
  for(var name in data) {
    urlEncodedDataPairs.push(encodeURIComponent(name) + '=' + encodeURIComponent(data[name]));
  }

  // We combine the pairs into a single string and replace all encoded spaces to 
  // the plus character to match the behaviour of the web browser form submit.
  urlEncodedData = urlEncodedDataPairs.join('&').replace(/%20/g, '+');

  // We setup our request
  XHR.open('POST', url);

  // We add the required HTTP header to handle a form data POST request
  XHR.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  XHR.setRequestHeader('Content-Length', urlEncodedData.length);
  console.log('sendData:', urlEncodedData, url);
  // And finally, We send our data.
  XHR.send(urlEncodedData);
}

function GoogleAuth(clientId, apiKey, loginButtonId, authCallback) {
    //Include script src="https://apis.google.com/js/client.js?onload=handleClientLoad"
    // authCallback(this.auth)
    this.clientId = clientId;
    this.apiKey = apiKey;
    this.loginButtonId = loginButtonId;
    this.authCallback = authCallback || null;
    this.scopes = 'https://www.googleapis.com/auth/userinfo.email';
    this.auth = null;
}

GoogleAuth.prototype.onLoad = function () {
    console.log('GoogleAuth.onLoad:');
    gapi.client.setApiKey(this.apiKey);
    window.setTimeout(this.requestAuth.bind(this, true), 5);
}


GoogleAuth.prototype.requestAuth = function (immediate) {
    console.log('GoogleAuth.requestAuth:');
    gapi.auth.authorize({client_id: this.clientId, scope: this.scopes, immediate: immediate},
                        this.onAuth.bind(this));
    return false;
}

GoogleAuth.prototype.onAuth = function (result) {
    console.log('GoogleAuth.onAuth:', result);
    var loginButton = document.getElementById(this.loginButtonId);
    if (!loginButton) {
        alert('No login button');
        return;
    }
    if (result && !result.error) {
        // Authenticated
        loginButton.style.display = 'none';
        gapi.client.load('plus', 'v1', this.requestUserInfo.bind(this));
    } else {
        // Need to authenticate
	loginButton.style.display = 'block';
        loginButton.onclick = this.requestAuth.bind(this, false);
        alert('Please login to proceed');
    }
}

GoogleAuth.prototype.requestUserInfo = function () {
    console.log('GoogleAuth.requestUserInfo:');
    var req = gapi.client.plus.people.get({userId: 'me'});
    req.execute(this.onUserInfo.bind(this));
}

GoogleAuth.prototype.onUserInfo = function (resp) {
    console.log('GoogleAuth.onUserInfo:', resp);
    if (!resp.emails || !resp.id)
        return;

    for (var j=0; j<resp.emails.length; j++) {
        var email = resp.emails[j];
        if (email.type == 'account') {
            this.auth = {email: email.value};
            break;
        }
    }
    if (!this.auth)
        return;
    this.auth.id = resp.id;
    var comps = resp.displayName.split(/\s+/);
    var name = (comps.length > 1) ? comps.slice(-1)+', '+comps.slice(0,-1).join(' ') : resp.displayName;
    this.auth.displayName = name || this.auth.email;
    this.auth.domain = resp.domain || '';
    this.auth.image = (resp.image && resp.image.url) ? resp.image.url : ''; 
    if (this.authCallback)
	this.authCallback(this.auth);
}

GoogleAuth.prototype.promptUserInfo = function () {
    var name = window.prompt('Enter a unique identifier or name');
    name = (name || '').trim();
    if (!name) {
	alert('Cancelled');
	return;
    }
    var email = (name.indexOf('@') >= 0) ? name : 'none@example.com';
    var id = name.replace(/[-.,'\s]+/g,'-').toLowerCase();
    this.onUserInfo({id: '#'+id, displayName: name,
		     emails: [{type: 'account', value:email}] });
}

function GoogleSheet(url, sheetName, fields) {
    this.url = url;
    this.fields = fields;
    this.sheetName = sheetName;
    this.headers = ['name', 'email', 'id', 'Timestamp'].concat(fields);
    this.created = null;
    this.callbackCounter = 0;
    this.columnIndex = {};
    for (var j=0; j<this.headers.length; j++)
        this.columnIndex[this.headers[j]] = j;
}

GoogleSheet.prototype.callback = function (callbackType, outerCallback, result, err_msg) {
    console.log('GoogleSheet: callback', callbackType, result, err_msg);
    this.callbackCounter -= 1;

    if (callbackType == 'createSheet')
        this.created = !!result;

    if (!result)
        console.log('GoogleSheet: '+callbackType+' callback: ERROR '+err_msg);

    if (outerCallback) {
        var retval = null;
        if (result && result.row)
            retval = (result.row.length == 0) ? {} : this.row2obj(result.row);
        outerCallback(retval, err_msg);
    }
}

GoogleSheet.prototype.row2obj = function(row) {
    if (row.length != this.headers.length) {
        console.log('GoogleSheet: row2obj: row length error: got '+row.length+' but expected '+this.headers.length);
        return null;
    }
    var obj = {};
    for (var j=0; j<row.length; j++)
        obj[this.headers[j]] = row[j];
    return obj;
}

GoogleSheet.prototype.obj2row = function(obj) {
    var row = [];
    var keys = Object.keys(obj);
    for (var j=0; j<this.headers.length; j++) {
        row.push(null);
    }
    for (var j=0; j<keys.length; j++) {
       var key = keys[j];
       if (!(key in this.columnIndex))
           throw('GoogleSheet: Invalid column header: '+key);
       row[this.columnIndex[key]] = obj[key];
    }
    return row;
}

GoogleSheet.prototype.checkCreated = function () {
    if (!this.created)
        throw('GoogleSheet: Sheet '+this.sheetName+' not created');
}

GoogleSheet.prototype.createSheet = function (callback) {
    var params = { sheet: this.sheetName, headers: JSON.stringify(this.headers) };
    this.callbackCounter += 1;
    GService.sendData(params, this.url, this.callback.bind(this, 'createSheet', callback));
}

GoogleSheet.prototype.putRow = function (rowObj, nooverwrite, callback, get, createSheet) {
    // Specify get to retrieve the existing/overwritten row.
    // Specify nooverwrite to not overwrite any existing row with same id
    // Get with nooverwrite will return the existing row, or the newly inserted row.
    if (createSheet && this.created == null) {
        // Call putRow after creating sheet
        this.createSheet( this.putRow.bind(this, rowObj, nooverwrite, callback, get) );
        return;
    }
    this.checkCreated();
    if (!rowObj.id || !rowObj.name)
        throw('GoogleSheet: Must provide id and name to put row');
    var row = this.obj2row(rowObj);
    var params = {sheet: this.sheetName, row: JSON.stringify(row)};
    if (nooverwrite)
        params['nooverwrite'] = '1';
    if (get)
        params['get'] = '1';
    this.callbackCounter += 1;
    GService.sendData(params, this.url, this.callback.bind(this, 'putRow', callback));
}

GoogleSheet.prototype.updateRow = function (updateObj, callback, get) {
    // Only works with existing rows
    // Specify get to return updated row
    this.checkCreated();
    if (!updateObj.id)
        throw('GoogleSheet: Must provide id to update row');
    var updates = [];
    var keys = Object.keys(updateObj);
    for (var j=0; j<keys.length; j++) {
       var key = keys[j];
       if (!(key in this.columnIndex))
           throw('GoogleSheet: Invalid column header: '+key);
       updates.push( [key, updateObj[key]] );
    }
    var params = {sheet: this.sheetName, id: updateObj.id, get: (get?'1':''), update: JSON.stringify(updates)};
    this.callbackCounter += 1;
    GService.sendData(params, this.url, this.callback.bind(this, 'updateRow', callback));
}

GoogleSheet.prototype.getRow = function (id, callback, createSheet) {
    // callback(obj, err_msg)
    // obj == null on error
    // obj == {} for non-existent row
    // obj == {id: ..., name: ..., } for returned row
    if (!callback)
        throw('GoogleSheet: Must specify callback for getRow');

    if (createSheet && this.created == null) {
        // Call getRow after creating sheet
        this.createSheet( this.getRow.bind(this, id, callback, null) );
        return;
    }
    this.checkCreated();
    var params = {sheet: this.sheetName, id: id, get: '1'};
    this.callbackCounter += 1;
    GService.sendData(params, this.url, this.callback.bind(this, 'getRow', callback));
}


function GoogleAuthSheet(url, sheetName, fields, auth) {
    if (!auth || !auth.id)
	throw('GoogleAuthSheet: Error - auth.id not defined!');
    this.gsheet = new GoogleSheet(url, sheetName, fields);
    this.auth = auth;
}

GoogleAuthSheet.prototype.extendObj = function (obj, fullRow) {
    var extObj = {};
    for (var j=0; j < this.gsheet.fields.length; j++) {
        var header = this.gsheet.fields[j];
        if (header in obj)
            extObj[header] = obj[header]
    }
    if ('Timestamp' in obj)
        extObj.Timestamp = obj.Timestamp;
    extObj.id = this.auth.id;
    if (fullRow) {
	extObj.name = this.auth.displayName;
	extObj.email = this.auth.email;
    }
    return extObj;
}

GoogleAuthSheet.prototype.createSheet = function (callback) {
    return this.gsheet.createSheet(callback);
}

GoogleAuthSheet.prototype.putRow = function (rowObj, nooverwrite, callback, get, createSheet) {
    return this.gsheet.putRow(this.extendObj(rowObj, true), nooverwrite, callback, get, createSheet);
}

GoogleAuthSheet.prototype.updateRow = function (updateObj, callback, get) {
    return this.gsheet.updateRow(this.extendObj(updateObj), callback, get);
}

GoogleAuthSheet.prototype.getRow = function (callback, createSheet) {
    return this.gsheet.getRow(this.auth.id, callback, createSheet);
}

GService.GoogleSheet = GoogleSheet;
GService.GoogleAuthSheet = GoogleAuthSheet;

GService.gauth = new GoogleAuth(CLIENT_ID, API_KEY, LOGIN_BUTTON_ID, AUTH_CALLBACK);

GService.onGoogleAPILoad = function () {
    console.log('GService.onGoogleAPILoad:');
    GService.gauth.onLoad();
}

})(GService, CLIENT_ID, API_KEY, LOGIN_BUTTON_ID, AUTH_CALLBACK);
