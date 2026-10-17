/** Modern lab assistance only. Never a historical procedure or actuator command. */
export function labControlGuidance(metrics,config){
  const error=metrics?.errorVectorDeg;
  if(!Array.isArray(error)||error.length!==3||!error.every(Number.isFinite)||!Number.isFinite(metrics.rateDegS))return {text:'Arm the separate lab to define a relative target.',keys:[]};
  if(Math.abs(error[2])>config.toleranceDeg && Math.hypot(error[0],error[1])<=config.toleranceDeg)return {text:'Residual error is on the unsupported roll axis. This fixture cannot command independent roll.',keys:[]};
  const keys=[];
  if(Math.abs(error[0])>config.toleranceDeg*.5)keys.push(error[0]>0?'yaw+':'yaw-');
  if(Math.abs(error[1])>config.toleranceDeg*.5)keys.push(error[1]>0?'pitch+':'pitch-');
  if(metrics.errorDeg<=config.toleranceDeg)return {text:metrics.rateDegS>config.maxRateDegS?'Inside target angle. Check signed rates and countersteer against the motion; release is neutral.':'Inside the angle and rate limits. Return the controller to neutral and watch the observed hold.',keys:[]};
  if(!keys.length)return {text:'Near the target. Watch total error and rotation rate; avoid a large input.',keys:[]};
  return {text:`Target relative to current attitude: ${error[0].toFixed(2)}° yaw, ${error[1].toFixed(2)}° pitch. Use the highlighted controller direction for a short input, then watch the rate.`,keys};
}

/** Existing service accepts discrete directions; a visual stick cannot add analog authority. */
export function stickDirections(x,y,deadband=.28){
  if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(deadband)||deadband<0||deadband>=1)throw new Error('Invalid controller displacement.');
  const axis=value=>Math.abs(value)<=deadband?0:Math.sign(value);
  return {yaw:axis(x),pitch:axis(-y)};
}
