<!--slidoc-options -->
# Slidoc: Additional documentation

- Plugins

- Scripted testing

---

## Plugins

Define plugins as a pseudo-Javascript block, with additional HTML
incorporated in comments.

```
<script type="x-slidoc-plugin"> Name = {
// Javascript function definitions
init: function() {...},
...
}

// Additional Javascript in anonymous namespace

/* HEAD:
<slidoc-script src="...">...</slidoc-script>
<style>...</style>

BUTTON: &#x260A;

TOP: 
<!--html-->
BODY:
<!--html-->
*/
// Name </script>
```

The comment `// Name` in the last line is optional. Any
`<slidoc-script>` elements in the `HEAD` portion will be treated as
standard `<script>` elements when the plugin is embedded.

The `Name` object is attached to a global object `Slidoc.PluginDefs` as
follows:

```
<script>(function() {
Slidoc.PluginDefs.Name = {
// Javascript function definitions
...
}
// Additional Javascript in anonymous namespace
})();
</script>
```

The comment portion with `HEAD`, `BUTTON`, `TOP`, `BODY` is
optional, and may be omitted for simple formula plugins. HTML template
text included in `TOP` and `BODY` and in the content when
[Embedding plugins](#) may contain MathJax as well
as python-style format strings of the form `%(plugin*)s` to customize
element IDs etc. (`TOP` content is inserted in the fixed menu overlay
at the top right corner, e.g., see `plugins/Timer.js`.)

[The following formats can be substituted in the template:]{#formats}

> `pluginSlideId`: `slidoc01-01`

> `pluginName`: `pluginName`

> `pluginLabel`: `slidoc-plugin-pluginName`

> `pluginId`: `slidoc01-01-plugin-pluginName`

> `pluginInitArgs`: argument string (See [Embedding plugins](#))

Note: Any percent (%) characters in the HTML templates may need to
escaped by doubling them (%%).

See `test/ex01-basic.md` and `test/ex06-plotly.md` for simple
examples. For more complex examples of pre-defined pugins, see
`plugins/Code.js` and `plugins/Slider.js`.

---

## Plugin object instances

Three types of objects are instantiated using `Slidoc.PluginDefs.name` as
the prototype:

1. `setup` objects: Instantiated once after document is ready

2. `global` objects: Instantiated after session has been
created/retrieved, and also after user switching (when grading)

3. `slide` objects: Instantiated for each slide where plugin is
embedded, after the `global` object has been instantiated.

The `this` object for each instance contains the following pre-defined
attributes:

> `this.name`: plugin name

> `this.userId`: user ID

> `this.displayName`: "LastName, FirstName ..."

> `this.gradableState`: *true* if grading

> `this.testUser`: *true* if test user

> `this.sessionName`: session name

> `this.siteName`: site name

> `this.remoteCall`: Invoke Python plugin of same name on server
> as `this.remoteCall(callback, arg1, ...)`

> `this.params`: plugin-specific command line parameters

> `this.initArgs`: list of init arguments for
> embedded plugin in the slide as values, e.g.,
> `[arg1, arg2, ...]`

The following are defined only for global and slide instances:

> `this.setup`:  setup instance

> `this.persist`: plugin-specific saved data for sessions 

> `this.paced`: True if paced session 

> `this.randomSeed`: slide-specific random seed (session-specific for global instances)

> `this.randomNumber`: random number generator using this seed
 
The following are defined only for slide instances:

> `this.global`: global instance (shared across all slides)

> `this.slideId`: `slidoc01-01`

> `this.slideNumber`: `1`

> `this.pluginId`: `slidoc-01-01-plugin-name`

> `this.qattributes`: question attributes objects (for question slides)

> `this.correctAnswer`: answer string (or null)

> `this.slideData`: object shared amongst all plugins in this slide

> `this.defined`: Parameters specified using Define: for the current slide

 For question slides, the text following `Answer:` will be accessible as
`this.qattributes.correct`.

Use `this.randomNumber()` to generate uniform random number between 0
and 1.  Use `this.randomNumber(min, max)` to pick equally probable
integer values between min and max (inclusive). Using these random
number generators ensures that randomized questions are reproducible
for the same session. The session would need to be reset to generate a
different set of questions. For non-paced sessions, reloading the web
page will automatically reset the session. Paced sessions will need to
be reset explicitly.

The following methods are automatically called for plugin instances;

> `initSetup(args)`: when setup instance is inititiated (after document is ready). May insert/modify DOM and plugin content.

> `initGlobal(args)`: when the global instance is instantiated (at start of session or user switching)

> `init(args)`: when the slide instance is instantiated

The following optional method, returning `true` or false, is invoked
on the global plugin instance each time remote access is requested to
for a plugin method:

> `allowRemoteAccess(methodName, fromAdmin)`: 

`initSetup` and `initGlobal` will be called with the *argument string*
from the first slide where the plugin occurs. Slide instance `init`
calls will use a parsed argument list. All the `init` calls will be in
a deterministic order, to preserve the sequence in which global random
generators may be called.

The following methods may be defined for plugins, as needed:

> `expect(intArg)`: returns expected correct answer (for formula plugins)

> `display(response, pluginResp)`: displays previously recorded user response (called at start/switch of session for each question)

> `disable(displayCorrect)`: disables plugin (after user response has been recorded)

> `response(intArg)`: records and returns user response

> `enterSlide(paceStart, backward)`: entering slide; returns slideDelay (in seconds) or null to use default (if paceStart only).

> `leaveSlide()`: leaving slide 

> `incrementSlide()`: incremental display of slide 

> `buttonClick()`: button corresponding to `BUTTON` unicode symbol has been clicked

Any plugin instance method may be invoked to handle event for elements
in the `BODY` by adding element attributes like

    onclick="Slidoc.Plugins.pluginName['%(pluginSlideId)s'].method(this);"


---

## Embedding plugins

Once defined, plugins may be embedded in one or more slides by
invoking its `init` method, with optional arguments, as follows:

```
=Name(arguments)
```

OR

```
<script type="x-slidoc-embed"> Name(arguments)
Optional HTML template content
</script>
```

This embeds the HTML BODY of the plugin at this location, in a `div` with `id`
set to `pluginId-body`, using templating to change element IDs. Any
HTML content between `<script type="x-slidoc-embed">..</script>`
is rendered within a `div`with `id` set to `pluginId-content`
(for the plugin to access/modify
during the `setup` instantiation.) In addition to the template
[formats](#) listed for `PluginBody`, an additional format
`%(pluginBody)s` may be used to specify where to include the plugin
body in the content (assumed to be HTML). If this format is omitted,
the content is assumed to be raw text and the plugin body is appended
after the content. (This raw text may be dynamically converted to HTML
by the plugin.)

The optional `arguments`, which must all be in the same line, are
supplied to the `init` call for slide instances. The `init` calls
occur in the same sequence in which the plugins are embedded in the
slide. A special object `$`, containing all previously
initialized plugin instances in the same slide, may be used in the
context of the arguments. For example, if the first embedded plugin is
`Alpha`, the the second plugin `Beta` may use the following arguments:

    =Beta($.Alpha.method(), $.Alpha.attribute).

Alternatively, using ``Name/*`` as the answer type automatically
embeds the plugin before the Answer (if it has not been explicitly
embedded before).

Another special object `$$` contains all global instances.

Multiple instances of plugins using the same definition can be present
a slide for use in formulas and for widgets, such as multiple
sliders. (Multiple instances are not allowed for response plugins and
reserved plugins.) Additional instances are referred to using plugin
names `pluginName-1`, `pluginName-2`, `pluginName-3` and so on. In
formulas, these can appear as `$.pluginName[1]`, `$.pluginName[2]` and
so on.

---

## Response plugins

Response plugins interact with the users and capture the response to a
question. They appears in the Answer portion of the slide in the form
`pluginName/contentType`:

    Answer: Code/python

    Answer: Upload/ipynb

The plugin should implement a `response(retry, callback)` method that
returns `true` on successful response and uses callback to return the
user response (as a string) and an optional `pluginResp` object of the
form:

`{name: pluginName, score: 1/0/0.75/.../null, answer: ans_plus_err,
invalid: invalid_msg, output:output, tests:0/1/2}`

`score` may be any value between `0.0` and `1.0`. A `null` value for
`score` implies no grading for the question. (The `score` will be
multiplied by the score weight for the question when computing the
cumulative score.) `invalid` is used to record syntax/runtime error
messages. `output` records valid (but possibly incorrect) output from
code testing. `tests` indicates whether zero, primary (output visible
to user), or secondary (output invisible to user) testing of code
output was carried out.

See `plugins/Code.js` for an example of a response plugin.

---

## Scripted testing

Use options `--test_script --pace=1` for scripted testing. (For
adaptive documents, use `--pace=2`).

Use query options of the form:

    name.html?testscript=basic&teststep=1&testuser=aaa&testkey=key

to trigger testing. `testscript` is the name of the script to run,
`testuser` is login id (which would be `grader` for grading). `testkey`
is the digest authentication key (a `testtoken` may also be provided instead.)
`teststep=1` enables stepwise testing, requiring user interaction.

At the beginning of the document to tested, include a script element of
of the form:

```
<script>
var TestScripts = {};
TestScripts.basic = [
  ['-ready'],
  ['+loginPrompt', 0, 500, 'login'],
  ['+lateTokenDialog', 0, 0, 'lateToken', ['none']],
  ['initSession', 0, 0, 'reset'],
  ['initSlideView', 2, 500, 'choice', ['D']],
  ['answerTally', 3, 500, 'input', [5.5]],
  ['answerTally', 11, 0, 'wait'],
  ['lastSlideDialog', 0, 0, 'dialogReturn', [true]],
  ['endPaced', 0, 0, 'end']
  ];
Slidoc.enableTesting(Slidoc.getParameter('testscript')||'', TestScripts);
</script>
```

The entry format is
`['expectedEvent', slide_number or 0, delay_msec or 0, 'action', [arg1, arg2, ...]]`,
with

> Prefix `+` for expected events indicates optional event (may not be reported)

> Prefix `-` for expected events indicates skipped event (no action to be performed)

See `test/ex??-*.md` for examples. See
`TestScript.prototype.eventAction` in `doc_test.js` for more testing
actions.



