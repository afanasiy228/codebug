#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<vector<int>> g(n);
    for(int i=0;i<m;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }

    vector<int> col(n,-1);
    queue<int> q;
    col[0]=0;
    q.push(0);

    while(!q.empty()) {
        int v=q.front();
        q.pop();
        for(int to:g[v]) {
            if(col[to]==-1) {
                col[to]=col[v]^1;
                q.push(to);
            }
            else if(col[to]==col[v]) {
                cout<<"NO\n";
                return 0;
            }
        }
    }

    cout<<"YES\n";

}
