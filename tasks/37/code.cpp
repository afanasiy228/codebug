#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<pair<int,int>> seg(n);
    for(int i=0;i<n;i++) cin>>seg[i].first>>seg[i].second;

    sort(seg.begin(), seg.end());

    int cnt=0;
    int last=-1e9;

    for(auto [l,r]:seg) {
        if(l>=last) {
            cnt++;
            last=r;
        }
    }

    cout<<cnt<<"\n";

}
