#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,q;
    if(!(cin>>n>>q)) return 0;
    vector<int>a(n+1);
    for(int i=1;i<=n;i++) cin>>a[i];

    unordered_set<int> st;

    while(q--) {
        int l,r;
        cin>>l>>r;
        for(int i=l;i<=r;i++) st.insert(a[i]);
        cout<<st.size()<<"\n";
    }

}
