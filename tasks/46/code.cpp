#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<vector<int>> g(n);

    for(int i=0;i<n-1;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    int q;
    cin>>q;

    vector<int> d(n,-1);
    queue<int> qq;
    d[0]=1;
    qq.push(0);

    while(!qq.empty()) {
        int v=qq.front();
        qq.pop();
        for(int to:g[v]) if(d[to]==-1) {
            d[to]=d[v]+1;
            qq.push(to);
        }
    }

    while(q--) {
        int v;
        cin>>v;
        cout<<d[v-1]<<"\n";
    }

}
