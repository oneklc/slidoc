<!--slidoc-defaults --features=assessment --prereqs=skip -->
# Test code execution

Test file

---

## Python function, single check

Write a function `sq(x)` that returns the square of `x`.

```
def sq(x):
    ...

```

Test it using the following call:

```python_test
print sq(2.5)
```

to produce the following output:

```nb_output
6.25
```

Answer: text/code=python

---

## Python function, double check

Write a function `sq(x)` that returns the square of `x`.

```
def sq(x):
    ...

```

Test it using the following call:

```python_test
print sq(2.5)
```

to produce the following output:

```nb_output
6.25
```

```python_test
# Additional tests
print sq(3.5)
```

```nb_output
12.25
```

Answer: text/code=python

---

## Javscript function, double check

Write a function `sq(x)` that returns the square of `x`.

```javascript
function sq(x) {
    ...
}
```

Test it using the following call:

```javascript_test
sq(2.5)
```

to produce the following output:

```nb_output
6.25
```

```javascript_test
// Additional tests
sq(3.5)
```

```nb_output
12.25
```

Answer: text/code=javascript

---

## Prior code 1 and 2

```python_input

Prior code1

```

```python_input

Prior code2

```

---

## Dummy question


```

Enter code using this template

```

```python_test
Test code1
```

```nb_output
Correct output
```

Type `Syntax error` to generate syntax error. 

Type `Semantic error` to generate incorrect output.

Anything else will generate correct output.

Answer: text/code=test

---

## Dummy question 2

Simulates semantic error in the test code

```

Enter code using this template

```

```python_test
Test code 2
Semantic error
```

```nb_output
Correct output
```

Type anything to generate incorrect output.

Answer: text/code=test

---

## Prior code 3 (with syntax error)

```python_input

Prior code 3
Syntax error

```

---

## Dummy question

Simulates syntax error in prior code

```

Enter code using this template

```

```python_test
Test code 3
```

```nb_output
Correct output
```

Type anything to generate syntax error.

Answer: text/code=test

---

## Last slide
