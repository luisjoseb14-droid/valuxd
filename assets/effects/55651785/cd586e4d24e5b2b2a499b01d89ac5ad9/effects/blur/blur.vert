#version 300 es
precision highp float;

in vec3 position;
in vec2 texcoord0;

out vec2 uv0;

uniform mat4 u_MVP;

void main() {
    gl_Position = vec4(sign(position.xy), 0.,1.0);
    uv0 = texcoord0;
}