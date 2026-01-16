#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string t,p;
    if(!(cin>>t>>p)) return 0;
    int cnt=0;
    size_t pos=0;

    while(true) {
        pos = t.find(p, pos);
        if(pos==string::npos) break;
        cnt++;
        pos += p.size();
    }

    cout<<cnt<<"\n";

}
