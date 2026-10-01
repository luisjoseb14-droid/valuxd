#version 300 es
precision highp float;

layout(location = 0) out vec4 FragColor;

in vec2 o_uv;

uniform sampler2D pageTex;
uniform sampler2D shadowTex;

uniform float alpha;

void main(void)
{
    vec2 uv0 = o_uv;
    uv0.y = 1.-uv0.y;
    vec4 pageCol = texture(pageTex, uv0);
    vec4 shadowCol = texture(shadowTex, uv0);
    shadowCol.rgb = vec3(0);
    shadowCol.a *= .25;
    vec4 res = pageCol;
    res = shadowCol * (1.-pageCol.a) + pageCol;
    // res = mix(shadowCol, pageCol, pageCol.a);
    res *= alpha;

    // res = shadowCol;
    // res = pageCol;
    FragColor = res;
}