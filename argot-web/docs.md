# Argonaut

An synergetic web-framework for business-critical single-file applications

There are two major components to Argonaut: DOM reconciliation and virtual-DOM memoization.

## Reconciliation

The first component lets you construct a snapshot of what the DOM should look like and apply it to the physical DOM:

```javascript
const my_vdom = elem("div", [
    elem("h1", ["Welcome to my cool app"]),
    elem("hr", []),
    elem("p", ["Isn't it cool?"]),
]);

render(document.getElementById("app-container"), my_vdom);
```

To update the DOM, `render` computes the difference between the active DOM and the virtual-DOM using a process called reconciliation and only mutates the DOM where changes were made.

The process of diffing is quite naïve: the algorithm simply compares each child of a DOM element to its corresponding virtual-DOM element and makes whatever changes are necessary to transform the DOM node into the virtual-DOM node. This means that, if you insert a node at the top of a child list, all nodes in the DOM will be re-rendered. This is not just bad for performance: a re-rendered node will likely lose user interactivity states such as focus and selection highlight. This can be avoided by giving the element which just got inserted a unique key, which helps reconciliation match elements during diffing. In general, anything which pops in and out of the virtual DOM dynamically should have a key.

To interact with the DOM in more complex ways, you can attach effects to your nodes:

```javascript
const my_element_ref = new Ref();

const my_vdom = elem("div", [
    elem("h1", [style("color", "red"), "Welcome to my cool app"]),
    elem("hr", []),
    elem("p", [setRef(my_element_ref), "Isn't it cool?"]),
    elem("button", [handler("click", () => alert("Hi!")), "Click me"]),
    effect("my_key", target => {
        console.log("This div was just created:", target);
        return () => console.log("This div was just deleted.");
    }),
]);

render(document.getElementById("app-container"), my_vdom);
my_element_ref.$.innerText = "hehe";
```

An effect is a special virtual-DOM node which can run code on the underlying DOM element after reconciliation is finished in response to element creations, deletions, and effect updates. See the reference documentation (the source code) for more detail.

`render` has only one memoization mechanism: if the old virtual-DOM structure has reference equality with the new virtual-DOM structure, the entire subtree is skipped. Although this is quite basic, pairing it with a competent memoization system can make re-rendering quite efficient.

## Memoization

Argonaut implements its virtual-DOM memoization system through one very powerful class: `Component`.

A `Component` serves three major duties: flagging dirty state, memoizing outputs, and managing derived instances.

A component's first duty is to keep track of changes to a given instance which one may wish to use dynamically while rendering a user interface. Whenever a change is made that a user may wish subscribe to, the component should call the `.dirty()` function:

```javascript
class PostList extends Component {
    constructor() {
        super();
        this.posts = [];
    }

    addPost(name) {
        this.posts.push(new PostState(name));
        this.dirty();
    }
}

class Post extends Component {
    constructor(name) {
        super();
        this.name = name;
    }

    makeItCapital() {
        this.name = this.name.toUpperCase();
        this.dirty();
    }
}
```

Calling the `.dirty()` function several times is very cheap so one should feel free to call it aggressively.

The `.dirty()` function is guaranteed to mark the instance as dirty, even if the actual instance hasn't changed. If you want to only call it when a property setter actually modifies something, you should use the `.dirtySet()` helper method instead:

```javascript
class Post extends Component {
    constructor(name) {
        super();
        this.name = name;
    }

    setName(value) {
        this.dirtySet("name", value);
    }
}
```

A component's second duty is to memoize computed values (frequently, a virtual DOM tree) and only recompute them when state upon which that value was computed becomes dirty. A component can provide a memoized value by overriding the optional `doRender` method:

```javascript
class Post extends Component {
    constructor(name) {
        super();
        this.name = name;
    }

    setName(value) {
        this.dirtySet("name", value);
    }

    doRender() {
        return elem("div", [
            elem("h1", [this.name]),
            elem("p", "This is a post."),
        ]);
    }
}

const my_post = new Component("whee");

const snapshot_1 = my_post.render();
console.assert(snapshot_1 === my_post.render());
my_post.setName("foo");
console.assert(snapshot_1 !== my_post.render());
```

By default, a component's computed value will be invalidated in two scenarios: the component itself became marked as `.dirty()` or a component it rendered during its own render handle became dirty. We can introduce additional data dependencies by calling a component's `.subscribe()` method in the render handler, which declares that the computed value depends on that component as well. `.subscribe()` just returns a reference to the method's receiver, making it easy to chain.

```javascript
class PostState extends Component {
    constructor(name) {
        super();
        this.name = name;
    }

    setName(value) {
        this.dirtySet("name", value);
    }
}

class PostView extends Component {
    constructor(state) {
        super();
        this.state = state;
    }

    doRender() {
        return elem("div", [
            elem("h1", [this.state.subscribe().name]),
            elem("p", "This is a post."),
        ]);
    }
}
```

As hinted above, a component does not necessarily have to render a virtual-DOM. Indeed, it could render any computed state:

```javascript
class PostState extends Component {
    constructor(name) {
        super();
        this.name = name;
        this.is_name_empty = new InlineComponent(
            () => this.subscribe().name.length === 0);
    }

    setName(value) {
        this.dirtySet("name", value);
    }
}

class PostView extends Component {
    constructor(state) {
        super();
        this.state = state;
    }

    doRender() {
        return elem("div", [
            elem("h1", [this.state.subscribe().name]),
            elem("p", this.state.is_name_empty.render() ? "Name is empty!" : "Name is not empty!"),
        ]);
    }
}
```

A component's final duty is to provide a mechanism for deriving a component instance from a key and persisting it between re-renders. This mechanism is provided using the `.deriveChild(namespace, key, ctor)` method, which takes a namespace identifier, a key, and a constructor closure. During a render, you can call `.deriveChild(namespace, key, ctor)` with a given namespace and key and, if that pair was computed on the previous render, it will return the instance it previously created. If the instance was not fetched during the previous render, the component (if previously extant) will be forgotten and created from scratch. Note that, as a convenience, the `ctor` field is optional and, if missing, will be defaulted to a closure instantiating `namespace` as if it were a class.

This is useful for rendering child components without having to create and delete them manually.

```javascript
class TodoList extends Component {
    constructor() {
        this.items = ["Use Argonaut", "Do insider trading", "Crush competition"];
    }
  
    doRender() {
        return elem("div", [
            elem("h1", ["My To-Do List"]),
            self.items.map((item, i) =>
                this.deriveChild(TodoItem, `item_${i}`, () => new TodoItem(item))
                    .render()
            ),
        ]);
    }
}

class TodoItem extends Component {
    constructor(text) {
        super();
        this.text = text;
    }

    doRender() {
        return elem("li", [this.text]);
    }
}
```

You can equivalently use the `.renderChild(namespace, key, prop_setter, ctor)` shorthand, which accepts an additional `prop_setter` field to set the properties of the child. If this is a closure, it will run that closure before rendering the component to give the user an opportunity to update the fields. If, instead, it's an object, it will use the keys of that object to `.dirtySet()` the properties of the child component.

```javascript
class MyInterface extends Component {
    constructor() {
        super();
        this.clicks = 0;
    }

    doRender() {
        return elem("div", [
            elem("h1", ["Fun Button Game!"]),
            this.renderChild(MyButton, "my_button", btn => {
                btn.text = "Clicks: " + this.clicks;
                btn.callback = () => {
                    this.clicks += 1;
                    this.dirty();
                };
                btn.dirty();
            }),
            this.renderChild(MyButton, "my_button", { text: "I don't do anything." }),
        ]);
    }
}

class MyButton extends Component {
    constructor() {
        super();
        this.text = "";
        this.callback = () => {};
    }

    doRender() {
        return elem("button", [handle("click", this.callback), this.text]);
    }
}
```

Finally, if you set the `key` to `null` or `undefined`, a key will be sequentially assigned to your derived children.

```javascript
class MyInterface extends Component {
    constructor() {
        super();
        this.clicks = 0;
    }

    doRender() {
        return elem("div", [
            elem("h1", ["Not-So-Fun Not-So-Button Game!"]),
            this.renderChild(MyLabel, null, { text: "I don't do anything." }),
            this.renderChild(MyLabel, null, { text: "I don't do anything either." }),
        ]);
    }
}

class MyLabel extends Component {
    constructor() {
        super();
        this.text = "";
    }

    doRender() {
        return elem("p", [this.text]);
    }
}
```

## Putting it Together

To put the two components of Argot together, you just have to write a repaint handler to continuously reconcile the page's state like so:

```javascript
const ROOT = new AppRoot();

function tick() {
    requestAnimationFrame(tick);
    render(app_container, ROOT.render());
}

requestAnimationFrame(tick);
```

And that's it! Now go! Become webshit programmers!


## Argot To-Do List

- [ ] Make `render` more exception-safe
- [ ] Ensure that `render` always runs hooks in a consistent manner and that they aren't interspersed with other volatile reconciliation code
- [ ] Ensure that effects are properly unmounted when the DOM node is destroyed externally
- [ ] Implement error absorption for components
- [ ] Make `elem` properly normalize its input
- [ ] Add more shorthand effects
