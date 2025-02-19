---
---

Programmers argue endlessly about the best way to format their programs,
but everyone agrees that the most important thing is to be <span i="coding style!importance of consistency">consistent</span>
<cite>Binkley2012,Johnson2019</cite>.
Since checking rules by hand is tedious,
most programmers use tools to compare code against various rules and report any violations.
Programs that do this are often called <span g="linter" i="linter; coding style!linter">linters</span>
in honor of an early one for <span i="C">C</span> named `lint`
(because it looked for fluff in source code).

In this chapter we will build a simple linter of our own inspired by <span i="ESLint">[ESLint][eslint]</span>,
which we use to check the code in this book.
Our tool will parse source code to create a data structure,
then go through that data structure and apply rules for each part of the program.
It will also introduce us to one of the key ideas of this book,
which is that source code is just another kind of data.

<div class="callout" markdown="1">

### Don't define your own style

Just as the world doesn't need more file format (<span x="regex-parser"/>)
it also doesn't need more programming styles,
or more arguments among programmers about whether there should be spaces before curly braces or not.
<span i="Standard JS">[Standard JS][standard-js]</span> may not do everything exactly the way you want,
but adopting it increases the odds that other programmers will be able to read your code at first glance.

</div>

## How can we parse JavaScript to create an AST?

A parser for a simple language like arithmetic or JSON is relatively easy to write.
A parser for a language as complex as JavaScript is much more work,
so we will use one called <span i="Acorn">[Acorn][acorn]</span> instead.
Acorn takes a string containing source code as input
and produces an <span g="abstract_syntax_tree" i="abstract syntax tree">abstract syntax tree</span> (AST)
whose nodes store information about what's in the program
(<span f="style-checker-parse-tree"/>).
An AST is for a program what the <span i="Document Object Model">DOM</span> is for HTML:
an in-memory representation that is easy for software to inspect and manipulate.

{% include figure
   id='style-checker-parse-tree'
   img='figures/parse-tree.svg'
   alt='A small parse tree'
   cap='The parse tree of a simple program.' %}

ASTs can be quite complex---for example,
the JSON representation of the AST for a single constant declaration
is {% include linecount file='parse-single-const.out' %} lines long:

{% include multi pat='parse-single-const.*' fill='js slice.out' %}

Acorn's output is in <span i="Esprima format">[Esprima][esprima] format</span>
(so-called because it was originally defined by a tool with that name).
The format's specification is very detailed,
but we can usually figure out most of what we need by inspection.
For example,
here is the output for a {% include linecount file='parse-const-func.js' %}-line program:

{% include multi pat='parse-const-func.*' fill='js slice.out' %}

{: .continue}
Yes, it really is almost 500 lines long…

## How can we find things in an AST?

If we want to find functions, variables, or anything else in an AST
we need to <span g="walk_tree" i="walk a tree">walk the tree</span>,
i.e.,
to visit each node in turn.
The [`acorn-walk`][acorn-walk] library will do this for us
using the <span i="Visitor pattern; design pattern!Visitor">Visitor design pattern</span> we first saw in <span x="page-templates"/>
If we provide a function to act on nodes of type `Identifier`,
`acorn-walk` will call that function each time it finds an identifier.
We can use other options to say that we want to record the locations of nodes (i.e., their line numbers)
and to collect comments in an array called `onComment`.
Our function can do whatever we want;
for demonstration purposes we will add nodes to an array called `state`
and report them all at the end
(<span f="style-checker-walk-tree"/>).

{% include figure
   id='style-checker-walk-tree'
   img='figures/walk-tree.svg'
   alt='Walking a tree'
   cap='Walking a tree to perform an operation at each node.' %}

{% include multi pat='walk-ast.*' fill='js out' %}

<div class="callout" markdown="1">

### There's more than one way to do it

`walk.simple` takes four arguments:

1.  The root node of the AST, which is used as the starting point.

2.  An object containing callback functions for handling various kinds of nodes.

3.  Another object that specifies what algorithm to use---we have set this to `null`
    to use the default because
    we don't particularly care about the order in which the nodes are processed.

4.  Something we want passed in to each of the node handlers,
    which in our case is the `state` array.
    If our node handling functions don't require any extra data
    from one call to the next
    we can leave this out;
    if we want to accumulate information across calls,
    this argument acts as the Visitor's memory.

Any general-purpose implementation of the Visitor pattern
is going to need these four things,
but as we will see below,
we can implement them in different ways.

</div>

## How can we apply checks?

We don't just want to collect nodes:
we want to check their properties against a set of rules.
One way to do this would be to call `walk.simple` once for each rule,
passing it a function that checks just that rule.
Another way---the one we'll use---is to write a <span i="software design!generic function">generic function</span>
that checks a rule and records any nodes that don't satisfy it,
and then call that function once for each rule inside our `Identifier` handler.
This may see like extra work,
but it ensures that all of our rule-checkers store their results in the same way,
which in turn means that we can write one reporting function
and be sure it will handle everything.

The function  `applyCheck` takes the current state (where we are accumulating rule violations),
a label that identifies this rule (so that violations of it can be stored together),
the node,
and a logical value telling it whether the node passed the test or not.
If the node failed the test
we make sure that `state` contains a list with the appropriate label
and then append this node to it.
This "create storage space on demand" pattern
is widely used but doesn't have a well-known name.

{% include keep file='check-name-lengths.js' key='applyCheck' %}

We can now put a call to `applyCheck` inside the handler for `Identifier`:

{% include keep file='check-name-lengths.js' key='main' %}

{: .continue}
We can't just use `applyCheck` as the handler for `Identifier`
because `walk.simple` wouldn't know how to call it.
This is a (very simple) example of the <span g="adapter_pattern" i="Adapter pattern; design pattern!Adapter">Adapter</span> design pattern:
we write a function or class to connect the code we want to call
to the already-written code that is going to call it.

The output for the same sample program as before is:

{% include file file='check-name-lengths.out' %}

{: .continue}
The exercises will ask why the parameter `x` doesn't show up
as a violation of our rule
that variables' names must be at least four characters long.

## How does the AST walker work?

The AST walker uses the Visitor pattern,
but how does it actually work?
We can build our own by defining a class with methods that walk the tree,
take action depending on the kind of node,
and then go through the children of that node (if any).
The user can then derive a class of their own from this
and override the set of action methods they're interested in.

One key difference between our implementation and `acorn-walk`'s is that
our methods don't need to take `state` as a parameter
because it's contained in the object that they're part of.
That simplifies the methods---one less parameter---but it does mean that
anyone who wants to use our visitor has to derive a class,
which is a bit more complicated than writing a function.
This tradeoff is a sign that managing state is part of the problem's
<span g="intrinsic_complexity" i="intrinsic complexity">intrinsic complexity</span>:
we can move it around,
but we can't get rid of it.

The other difference between our visitor and `acorn-walk` is that
our class uses <span g="dynamic_lookup" i="dynamic lookup">dynamic lookup</span>
(a form of <span i="introspection!of methods">introspection</span>)
to look up a method
with the same name as the node type in the object.
While we normally refer to a particular method of an object using `object.method`,
we can also look them up by asking for `object[name]`
in the same way that we would look up any other property of any other object.
Our completed class looks like this:

{% include keep file='walker-class.js' key='walker' %}

The code we need to use it is:

{% include erase file='walker-class.js' key='walker' %}

{: .continue}
and its output is:

{% include file file='walker-class.out' %}

We think this approach to implementing the Visitor pattern is easier to understand and extend
than one that relies on callbacks,
but that could just be a reflection of our background and experience.
As with code style,
the most important thing is consistency:
if we implement Visitor using classes in one place,
we should implement it that way everywhere.

## How else could the AST walker work?

A third approach to this problem uses
the <span g="iterator_pattern" i="Iterator pattern; design pattern!Iterator">Iterator</span> design pattern.
Instead of taking the computation to the nodes as a visitor does,
an iterator returns the elements of a complex structure one by one for processing
(<span f="style-checker-iterator"/>).
One way to think about it is that the Visitor pattern encapsulates recursion,
while the Iterator pattern turns everything into a `for` loop.

{% include figure
   id='style-checker-iterator'
   img='figures/iterator.svg'
   alt='The Iterator pattern'
   cap='Finding nodes in the tree using the Iterator pattern.' %}

We can implement the Iterator pattern in JavaScript using
<span g="generator_function" i="generator function; Iterator pattern!generator function">generator functions</span>.
If we declare a function using `function *` (with an asterisk) instead of `function`
then we can use the `yield` keyword to return a value and suspend processing to be resumed later.
The result of `yield` is a two-part structure with a value and a flag showing whether or not processing is done:

{% include multi pat='generator-example.*' fill='js out' %}

{: .continue}
A generator function doesn't actually generate anything;
instead,
it creates an object that we can then ask for values repeatedly.
This gives us a way to have several generators in play at the same time.

As another example,
this generator takes a string and produces its vowels one by one:

{% include multi pat='generator-vowels-while.*' fill='js out' %}

Instead of a `while` loop it is much more common to use `for...of`,
which knows how to work with generators:

{% include keep file='generator-vowels-for.js' key='loop' %}

Finally,
just as `function *` says "this function is a generator",
`yield *` says "yield the values from a nested generator one by one".
We can use it to walk irregular structures like nested arrays:

{% include file file='generator-tree.js' %}

Let's use generators to count the number of expressions of various types in a program.
The generator function that visits each node is:

{% include keep file='generator-count.js' key='generator' %}

{: .continue}
and the program that uses it is:

{% include keep file='generator-count.js' key='main' %}

When we run it with our usual test program as input, we get:

{% include file file='generator-count.out' %}

Generators are a clean solution to many hard problems,
but we find it more difficult to check variable identifiers using generators
than using the class-based Visitor approach
because we want to accumulate violations to report later.
Again,
this could be a reflection of what we're used to rather than anything intrinsic;
as with coding style,
the most important thing is to be consistent.

## What other kinds of analysis can we do?

As one final example,
consider the problem of keeping track of which methods are defined where
in a deeply-nested class hierarchy.
(This problem comes up in some of the later chapters in this book:
we wrote so many classes that incrementally extended their predecessors for pedagogical purposes
that we lost track of what was defined where.)
To create a table of method definitions,
we first need to find the ancestors of the last class in the hierarchy:

{% include erase file='find-ancestors.js' key='skip' %}

Finding class definitions is a straightforward extension of what we have already done:

{% include keep file='find-ancestors.js' key='findClassDef' %}

To test this code, we start with the last of these three short files:

{% include multi pat='*.js' fill='upper middle lower' %}
{% include file file='run-find-ancestors.out' %}

Good: we can recover the <span i="chain of inheritance">chain of inheritance</span>.
Finding method definitions is also straightforward:

{% include file file='find-methods.js' %}

And finally,
we can print a <span g="markdown" i="Markdown">Markdown</span>-formatted table
showing which methods are defined in which class:

{% include file file='run-find-methods.raw.out' %}

{: .continue}
which renders as:

<div class="latex" command="\vspace{\baselineskip}"/>

| method | Upper | Middle | Lower |
| ---- | ---- | ---- | ---- |
| additional | . | . | X |
| constructor | X | X | . |
| modify | X | X | . |
| report | X | . | X |

<div class="latex" command="\vspace{\baselineskip}"/>

This may seem rather pointless for our toy example,
but it proves its worth when we are looking at something like
the virtual machine we will build in <span x="virtual-machine"/>,
which has a more complex method definition table:

<div class="latex" command="\vspace{\baselineskip}"/>

| method | DebuggerBase | DebuggerInteractive | DebuggerTest | DebuggerExit |
| ---- | ---- | ---- | ---- | ---- |
| clear | . | X | . | . |
| constructor | X | X | X | . |
| exit | . | X | . | X |
| getCommand | . | X | . | . |
| handle | . | X | . | . |
| help | . | X | . | . |
| input | . | X | X | . |
| interact | . | X | . | . |
| list | . | X | . | . |
| message | X | . | X | . |
| next | . | X | . | . |
| print | . | X | . | . |
| run | . | X | . | . |
| setTester | . | . | X | . |
| setVM | X | . | . | . |
| stop | . | X | . | . |
| variables | . | X | . | . |
