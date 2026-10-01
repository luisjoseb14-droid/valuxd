#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;

out vec2 o_uv;
out float o_CurTextLine;

uniform mat4 u_MVP;
uniform float horizontal;

void main() {
  gl_Position = u_MVP * vec4(position.xy, 0.0, 1.0);
  o_CurTextLine = position.z;
  o_uv = texcoord0;
  if (horizontal < 0.5) {
    if (o_uv.x < 0.5 && o_uv.y < 0.5)
      o_uv = vec2(1, 0);
    else if (o_uv.x < 0.5 && o_uv.y > 0.5)
      o_uv = vec2(0, 0);
    else if (o_uv.x > 0.5 && o_uv.y > 0.5)
      o_uv = vec2(0, 1);
    else if (o_uv.x > 0.5 && o_uv.y < 0.5)
      o_uv = vec2(1, 1);
  }
}
