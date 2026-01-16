#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long ax,ay,bx,by,cx,cy;
    if(!(cin>>ax>>ay>>bx>>by>>cx>>cy)) return 0;

    long long cross = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax);

    if(cross>0) cout<<"RIGHT\n";
    else if(cross<0) cout<<"LEFT\n";
    else cout<<"COLLINEAR\n";

}
