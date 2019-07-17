const acorn = require('acorn')
const walk = require('acorn-walk')

const program = `// Constant
const value = 2

// Function
const double = (x) => {
  const y = 2 * x
  return y
}

// Main body
const result = double(value)
console.log(result)
`

const applyCheck = (state, label, node, passes) => {
  if (!passes) {
    if (!state.hasOwnProperty(label)) {
      state[label] = []
    }
    state[label].push(node)
  }
}

const ast = acorn.parse(program, {locations: true})

const state = {}
walk.simple(ast, {
  Identifier: (node, state) => {
    applyCheck(state, 'name_length', node, node.name.length >= 4)
  }
}, null, state)

state.name_length.forEach(
  node => console.log(`${node.name} at line ${node.loc.start.line}`))
