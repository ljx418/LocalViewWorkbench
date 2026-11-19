const assert = require('node:assert/strict');
const {hostReady, waitForHost, dismissStartupTemplates} = require('./v0_s2_browser_readiness.cjs');
(async () => {
 const app={loadGraphData(){},graph:{},canvas:{},configuringGraph:false,pendingGraphLoads:new Set(),graphLoadSequence:1,committedGraphLoadSequence:1};
 global.window={comfyAPI:{app:{app}}};
 assert.equal(hostReady(),false); // Legacy canvas alone precedes Pinia setup.
 window.app=app;window.graph=app.graph;assert.equal(hostReady(),true);
 app.pendingGraphLoads.add(2);assert.equal(hostReady(),false);app.pendingGraphLoads.clear();
 app.configuringGraph=true;assert.equal(hostReady(),false);app.configuringGraph=false;
 app.committedGraphLoadSequence=0;assert.equal(hostReady(),false);app.committedGraphLoadSequence=1;
 app.graphLoadSequence=0;app.committedGraphLoadSequence=0;assert.equal(hostReady(),false);
 app.graphLoadSequence=1;app.committedGraphLoadSequence=1;
 window.graph={};assert.equal(hostReady(),false);window.graph=app.graph;
 assert.equal(hostReady(),true);
 let called=0;
 await waitForHost({async waitForFunction(predicate,arg,options){called++;assert.equal(predicate,hostReady);assert.equal(arg,null);assert.equal(options.timeout,60000);assert.equal(predicate(),true);}});
 assert.equal(called,1);delete global.window;
 const actions=[];
 await dismissStartupTemplates({locator(selector){assert.equal(selector,'[data-testid="template-workflows-content"]');return{async waitFor(options){actions.push(options.state);}};},
  keyboard:{async press(key){assert.equal(key,'Escape');actions.push(key);}},async waitForFunction(){actions.push('ready');}});
 assert.deepEqual(actions,['visible','Escape','hidden','ready']);
 console.log('Native host readiness boundaries passed; no browser/model started.');
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
