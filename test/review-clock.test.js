import test from 'node:test'
import assert from 'node:assert/strict'
import {frameBoundary, noteRange} from '../review-assets/desk/clock.js'

test('36 actual grid steps recover the boundary despite microsecond browser readback truncation', () => {
  let current = 0
  let stepped
  for (let index = 0; index < 36; index++) {
    const boundary = frameBoundary(current, 1/30, 1, 3)
    current = Math.floor(boundary.exactSeconds * 1e6) / 1e6
    stepped = {...boundary, browserSeconds:current}
  }
  assert.equal(stepped.ordinal, 36)
  assert.deepEqual(noteRange(current, 1/30, stepped), {startUs:1200000,endUs:1233333})
})

test('a manual seek, playback movement or coarse browser time never reuses an old stepped point', () => {
  const stepped = {...frameBoundary(35/30, 1/30, 1), browserSeconds:1.2}
  assert.deepEqual(noteRange(1.210123456,1/30,stepped),{startUs:1210123,endUs:1243457})
  assert.deepEqual(noteRange(1.3,1/30,stepped),{startUs:1300000,endUs:1333333})
  assert.deepEqual(noteRange(1.198,1/30,{...stepped,browserSeconds:1.198}),{startUs:1198000,endUs:1231333})
  assert.deepEqual(noteRange(1.210123456,1/30,null),{startUs:1210123,endUs:1243457})
})

test('fractional rates, reverse steps and video boundaries retain integer grid identities', () => {
  const step=1001/30000
  let current=0
  let boundary
  for(let index=0;index<300;index++) {
    boundary=frameBoundary(current,step,1,20)
    current=Math.floor(boundary.exactSeconds*1e6)/1e6
  }
  assert.equal(boundary.ordinal,300)
  assert.deepEqual(noteRange(current,step,{...boundary,browserSeconds:current}),{startUs:10010000,endUs:10043367})
  assert.equal(frameBoundary(current,step,-1,20).ordinal,299)
  assert.equal(frameBoundary(0,1/30,-1,3).ordinal,0)
  const last=frameBoundary(3,1/30,1,3)
  assert.equal(last.ordinal,89)
  assert.deepEqual(noteRange(last.exactSeconds,1/30,{...last,browserSeconds:last.exactSeconds}),{startUs:2966667,endUs:3000000})
  assert.throws(()=>frameBoundary(0,0,1),RangeError)
})
