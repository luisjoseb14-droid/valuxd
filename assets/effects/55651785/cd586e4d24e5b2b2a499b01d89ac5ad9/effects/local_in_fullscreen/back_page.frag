#version 300 es
precision highp float;

layout(location = 0) out vec4 FragColor;

in vec2 v_local_uv;
in vec2 v_screen_uv;
in vec2 m;
in vec2 n;

uniform sampler2D _MainTex;

uniform vec2 inCornerPosition;
uniform vec2 inFoldPosition;
uniform float foldRadius;

uniform vec4 u_ScreenParams;

uniform float direction;
uniform float relief;
uniform float contrast;
uniform float blendWithOriginal;
void Carvings(sampler2D _tex, vec2 i_uv, float _dir, float _relief, 
            float _contrast, float _blend, vec2 _screen_size, out vec4 o_res)
{
    vec2 unit = vec2(1./720.);
    unit.x *= _screen_size.x/_screen_size.y;

    float a = radians(_dir);
    vec2 offset = vec2(cos(a), sin(a))*_relief;
    vec4 ori_col = texture(_tex, i_uv);
    vec4 cur_col = texture(_tex, vec2(i_uv + unit * offset));
    cur_col.rgb = (cur_col.rgb - .5) * _contrast / 60.;         // ae: 60 -> editor: 1
    vec4 offset_col = texture(_tex, vec2(i_uv - unit * offset));
    offset_col.rgb = (offset_col.rgb - .5) * _contrast / 60.;
    vec4 neg_col = vec4(1.-offset_col.rgb, offset_col.a);
    
    o_res = cur_col;
    o_res.rgb = (cur_col.rgb + neg_col.rgb) * .5;
    o_res.rgb = mix(o_res.rgb, ori_col.rgb, _blend);
}

vec2 Mirror(vec2 x) { return abs(mod(x-1., 2.)-1.); }
float cut(vec2 u) {return step(0., u.x)*step(u.x, 1.)*step(0., u.y)*step(u.y, 1.); }

#define PI 3.14159265359
#define EPSILON 1e-8

float my_cross(vec2 a, vec2 b) {
    return a.x * b.y - a.y * b.x;
}

const float QUAD_SCALE_VALUE = 0.77;

float get_distance_from_pt2line(vec2 _pt, vec3 _l){ return abs(_l.x*_pt.x+_l.y*_pt.y+_l.z)/sqrt(_l.x*_l.x+_l.y*_l.y); }

vec2 mirror_pt_by_line(vec2 _pt, vec3 _line) {
    float a = _line.x; float b = _line.y; float c = _line.z;
    float d = get_distance_from_pt2line(_pt, _line);
    float x = ((b*b-a*a)*_pt.x-2.*a*(b*_pt.y+c))/(a*a+b*b);
    float y = ((a*a-b*b)*_pt.y-2.*b*(a*_pt.x+c))/(a*a+b*b);
    return vec2(x, y);
}

vec2 mirror_uv_in_box(vec2 _pt, vec3 _line){
    vec2 new_uv = mirror_pt_by_line(_pt, _line);
    if(new_uv.x > 1. || new_uv.y > 1. || new_uv.x < 0. || new_uv.y < 0.){
        return _pt;
    }
    return new_uv;
}

vec2 projection_from_pt2line(vec2 _pt, vec3 _line){     // 
    float a = _line.x; float b = _line.y; float c = _line.z; float d = a*_pt.y-b*_pt.x;
    float x = (-a*c-b*d)/(a*a+b*b);
    float y = (-c-a*x)/(b+EPSILON);
    return vec2(x, y);
}

vec3 get_line_from2pt(vec2 _a, vec2 _b) {       // 
    float a = _a.y-_b.y;
    float b = _b.x-_a.x;
    float c = _a.x*_b.y-_a.y*_b.x;
    return vec3(a,b,c);
}

vec4 get_parallel_line_from_distance(vec3 _line, float _d){
    float a = _line.x;
    float b = _line.y;
    float c = _line.z;
    float tmp = sqrt(a*a+b*b);
    float up_line_c = _d*tmp+c;
    float down_line_c = c-_d*tmp;
    return vec4(a, b, up_line_c, down_line_c);
}

const float LINE_WIDTH = 0.001;
void DrawLine(vec2 _u, vec3 _line, vec3 _col, float _line_width, inout vec4 res){
    float d = get_distance_from_pt2line(_u, _line);
    d = step(d, _line_width);
    res += vec4(vec3(d)*_col, d);
}

const float classic_ui = 1.;

void cylinder_mapping(vec2 _u, vec2 _corner_pos, vec2 _fold_pos, float _fold_radius, vec2 _extra_size, inout vec4 res)
{
    vec2 uv = _u;

    vec2 cp = _corner_pos;
    vec2 fp = vec2(_fold_pos.x, max(_fold_pos.y, 0.));
    if(cp.y >= 1.) cp.y = max(fp.y+0.001, cp.y);
    if(cp.y <= 0.) cp.y = min(fp.y-0.001, cp.y);
    if(cp.x >= 1.) cp.x = max(fp.x+0.001, cp.x);
    if(cp.x <= 0.) cp.x = min(fp.x-0.001, cp.x);
    float fr = max(_fold_radius, EPSILON);
    vec2 fold_dir = normalize(fp-cp);
    
    vec2 center_pt = (cp+fp)*0.5;

    //////////////////////// Basic Line //////////////////////////
    vec3 line1 = get_line_from2pt(cp, fp);              // ax+by+c=0
    vec3 line2 = vec3(line1.y, -line1.x, line1.x*center_pt.y-line1.y*center_pt.x);
    vec3 line_for_fp = vec3(line1.y, -line1.x, line1.x*fp.y-line1.y*fp.x);
    if(classic_ui > 0.5) line_for_fp = get_parallel_line_from_distance(line2, 0.).xyw;

    // DrawLine(uv, line1, vec3(1,0,0), LINE_WIDTH, res);
    // DrawLine(uv, line2, vec3(0,1,0), LINE_WIDTH, res);
    // DrawLine(uv, line_for_fp, vec3(0,0,1), LINE_WIDTH, res);

    float fold_length = PI*fr*0.5;
    float k = sign(line_for_fp.x/(line_for_fp.y+EPSILON));     // >0=>\, <0=>/

    vec3 line_curl1 = get_parallel_line_from_distance(line2, fold_length).xyw;
    vec3 line_curl2 = get_parallel_line_from_distance(line_curl1, fr).xyz;

    float fold_outer = 0.;
    if(k < 0.){        // line for /
        if(line_for_fp.z-line_curl1.z>0.){
            line_curl1.z = line_for_fp.z;
            line_curl2 = get_parallel_line_from_distance(line_curl1, fr).xyz;
            fold_outer = 1.;
        }
    }else{                  // line for 
        if(line_curl1.z-line_for_fp.z<0.){
            line_curl1.z = line_for_fp.z;
            line_curl2 = get_parallel_line_from_distance(line_curl1, fr).xyz;
            fold_outer = 1.;
        }
    }

    // DrawLine(uv, line_curl1, vec3(1,0.5,0.8), LINE_WIDTH*3., res);
    // DrawLine(uv, line_curl2, vec3(1,0.5,0.5), LINE_WIDTH*3., res);
    vec2 p1 = vec2((-line_curl1.z-line_curl1.y*cp.y)/(line_curl1.x+EPSILON), cp.y);
    vec2 p2 = vec2(cp.x, (-line_curl1.z-line_curl1.x*cp.x)/(line_curl1.y+EPSILON));
    
    if(k > 0.){
        vec2 t = p1;
        p1 = p2;
        p2 = t;
    }
    float bottom_flat_mask = my_cross(p1-p2, p1-uv)>0.?1.:0.;     // clockwise>0，counterclockwise<0

    //////////////////// Bottom Curl Uv Mapping && Texturing /////////////////////////////////
    float d_from_curl_line1 = get_distance_from_pt2line(uv, line_curl1);
    float theta = asin(d_from_curl_line1/fr) * step(d_from_curl_line1, fr+0.001);
    float curl_length = theta * fr;
    vec2 curl_uv = uv + normalize(-fold_dir)*(curl_length-d_from_curl_line1);
    curl_uv = clamp(curl_uv, vec2(-10.), vec2(10.));

    // vec2 bottom_uv = mix(curl_uv * cut(curl_uv), uv, bottom_flat_mask);
    // bottom_uv -= 0.5;
    // bottom_uv /= QUAD_SCALE_VALUE;
    // if(_extra_size.x<_extra_size.y){
    //     bottom_uv.x /= _extra_size.x/_extra_size.y;
    // }else{
    //     bottom_uv.y /= _extra_size.y/_extra_size.x;
    // }
    // bottom_uv += 0.5;
    // vec4 bottom_col = texture(_MainTex, bottom_uv);
    // bottom_col *= clamp(bottom_flat_mask+cut(curl_uv), 0., 1.);
    // bottom_col = mix(
    //     bottom_col*bottom_flat_mask,
    //     bottom_col*step(d_from_curl_line1, fr+0.0001),
    //     (bottom_col*step(d_from_curl_line1, fr+0.0001)).a
    // );

    vec3 fold_line = line2;
    if(fold_outer>0.5) fold_line = get_parallel_line_from_distance(line_curl1, fold_length).xyz;
    vec2 mirror_uv = mirror_pt_by_line(uv, fold_line);
    float mirror_mask = bottom_flat_mask * cut(mirror_uv);

    vec2 mirror_upside_curl_uv = mirror_pt_by_line(curl_uv, fold_line);
    float mirror_upside_mask = cut(mirror_upside_curl_uv) * (1.-bottom_flat_mask);
    mirror_upside_mask *= step(d_from_curl_line1, fr+0.001);

    vec2 upside_uv = mix(
        mirror_uv,
        mirror_upside_curl_uv,
        mirror_upside_mask
    );
    upside_uv -= 0.5;
    upside_uv /= QUAD_SCALE_VALUE;
    if(_extra_size.x<_extra_size.y){
        upside_uv.x /= _extra_size.x/_extra_size.y;
    }else{
        upside_uv.y /= _extra_size.y/_extra_size.x;
    }
    upside_uv += 0.5;
    vec4 upside_col = texture(_MainTex, upside_uv);
    // vec4 upside_col = vec4(0);
    // Carvings(_MainTex, upside_uv, direction, relief, 
    //         contrast, blendWithOriginal, u_ScreenParams.xy, upside_col);
    upside_col *= clamp(mirror_upside_mask+mirror_mask, 0., 1.);

    res = mix(upside_col, res, res.a);
    // res = mix(bottom_col, res, res.a);
}

uniform vec4 u_color;

void main(void)
{
    //zhe kuai bu yong dong, shi pei yong//
    vec2 uv = v_local_uv;
    vec2 x = vec2(0.0);
    vec2 y = vec2(0.0);
    x = (m + n) / (2.0 * (v_screen_uv));
    y = (m - n) / (2.0 * (1. - v_screen_uv));
    float adapt_width = x.x - y.x;
    float adapt_height = x.y - y.y;
    uv.x -= (x.x + y.x) * 0.5;
    uv.y += (x.y + y.y) * 0.5;
    uv.x /= (adapt_width * 0.5);
    uv.y /= (adapt_height * 0.5);
    uv = uv * 0.5 + 0.5;

    vec2 quad_uv = uv;
    quad_uv -= 0.5;
    if(adapt_width<adapt_height){
        quad_uv.x *= adapt_width/adapt_height;
    }else{
        quad_uv.y *= adapt_height/adapt_width;
    }
    quad_uv *= QUAD_SCALE_VALUE;
    quad_uv += 0.5;
    //----------------------------//

    vec2 uv0 = uv;
    // vec4 mainColor = texture(_MainTex, uv0);
    vec4 res = vec4(0);
    vec2 extra_size = vec2(adapt_width, adapt_height);
    // extra_size = vec2(1);
    // quad_uv = uv0;
    cylinder_mapping(quad_uv, inCornerPosition, inFoldPosition, foldRadius, extra_size, res);
    // res = mix(vec4(uv0,0,1), res, res.a);
    res = clamp(res, vec4(0), vec4(1));
    res *= cut(quad_uv);
    // res = texture(_MainTex, uv0);
    // res = vec4(foldRadius,0,0,1);
    // res = texture(_MainTex, uv0) * u_color;
    FragColor = res;
}