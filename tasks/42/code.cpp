#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<vector<int>> g(n);
    vector<int> indeg(n,0);

    for(int i=0;i<m;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        indeg[v]++;
    }

    queue<int> q;
    for(int i=0;i<n;i++) if(indeg[i]==0) q.push(i);

    vector<int> order;
    while(!q.empty()) {
        int v=q.front();
        q.pop();
        order.push_back(v);
        for(int to:g[v]) if(--indeg[to]==0) q.push(to);
    }

    for(int i=0;i<n;i++) cout<<order[i]+1<<" ";
    cout<<"\n";

}
