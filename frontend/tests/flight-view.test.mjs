import test from 'node:test';
import assert from 'node:assert/strict';
import {flightViewModel,renderFlightView} from '../dist/flight-view.mjs';
const craft={altitudeM:1000,downrangeM:100,pitchDeg:20,verticalSpeedMps:-10,horizontalSpeedMps:5,horizontalVelocityMps:5};
const engine={enabled:true,thrustN:10000};
test('projection uses server altitude and downrange without advancing physical state',()=>{
 const value=structuredClone(craft);const view=flightViewModel(value,engine,{heightM:2000,widthM:1000});assert.equal(view.x,430);assert.equal(view.y,200);assert.deepEqual(value,craft);assert.equal(view.mode,'EDUCATIONAL_PHYSICS_LAB');
});
test('zero altitude reaches the surface; negative altitude is not visual extrapolation',()=>{
 assert.equal(flightViewModel({...craft,altitudeM:0},engine).y,330);assert.equal(flightViewModel({...craft,altitudeM:-1},engine).y,330);
});
test('out-of-view data is disclosed and missing telemetry rejected',()=>{
 assert.equal(flightViewModel({...craft,downrangeM:1e6},engine).clipping,true);assert.throws(()=>flightViewModel({...craft,altitudeM:NaN},engine));
});
test('exhaust visualization requires actual enabled nonzero thrust',()=>{
 assert.equal(flightViewModel(craft,{enabled:false,thrustN:10000}).thrusting,false);assert.equal(flightViewModel(craft,{enabled:true,thrustN:0}).thrusting,false);
});
function dom() {
 const nodes=new Map();for(const id of ['flight-craft','flight-plume','flight-empty','flight-height-label','flight-projection-note','flight-velocity']) nodes.set('#'+id,{attributes:{},setAttribute(key,value){this.attributes[key]=value;},removeAttribute(key){delete this.attributes[key];},textContent:''});
 return {querySelector:selector=>nodes.get(selector)};
}
test('positive physical pitch renders toward negative downrange',()=>{
 const root=dom();renderFlightView(root,craft,engine,{heightM:2000,widthM:1000});assert.match(root.querySelector('#flight-craft').attributes.transform,/rotate\(-20\)/);
});
test('signed measured velocity drives the arrow without a trajectory prediction',()=>{
 const root=dom();renderFlightView(root,craft,engine);assert.match(root.querySelector('#flight-velocity').attributes.d,/ l10 20$/);assert.equal(root.querySelector('#flight-plume').attributes.visibility,'visible');
});
test('unavailable signed horizontal velocity hides the arrow instead of guessing',()=>{
 const root=dom();const missing={...craft};delete missing.horizontalVelocityMps;renderFlightView(root,missing,engine);assert.equal(root.querySelector('#flight-velocity').attributes.hidden,'');
});
